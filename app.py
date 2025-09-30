from flask import Flask, render_template, request, redirect, url_for, flash, abort, session
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import database
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os
import json
import requests
from urllib.parse import urlencode
import logging
from datetime import timedelta
import time  # Added to resolve NameError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Database imports and table creation
from database import (
    get_db_connection,
    get_user_details,
    get_user_by_id,
    update_user_profile,
    update_user_password,
    create_tables
)

# Create tables if they don't exist
create_tables()

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'Fliph106')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=30)
app.config['SESSION_COOKIE_SECURE'] = True  # True for Render HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_COOKIE_PATH'] = '/'
app.config['REMEMBER_COOKIE_DURATION'] = timedelta(days=7)
app.config['SESSION_COOKIE_NAME'] = 'buyMoSession'

# PayFast Configuration
PAYFAST_MERCHANT_ID = "10039066"
PAYFAST_MERCHANT_KEY = "gz01ogc2pu5bp"
PAYFAST_URL = "https://sandbox.payfast.co.za/eng/process"
PAYFAST_RETURN_URL = "https://buymo.onrender.com/payfast/return"
PAYFAST_CANCEL_URL = "https://buymo.onrender.com/cart"
PAYFAST_NOTIFY_URL = "https://buymo.onrender.com/payfast/notify"

@app.template_filter('zar')
def format_zar(amount):
    if amount is None:
        return "R0.00"
    try:
        return f"R{float(amount):,.2f}".replace(",", " ")
    except (ValueError, TypeError):
        return "R0.00"

# Configure upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['UPLOAD_FOLDER_PROFILES'] = 'static/uploads/profiles'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Routes
@app.route('/')
def index():
    return redirect(url_for('signup'))

@app.route('/get-started')
def get_started():
    return render_template('get_started.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        user = database.get_user_by_email(email)
        if user:
            flash('Email already registered. Please login.')
            return redirect(url_for('login'))

        database.create_user(username, email, password)
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user_data = database.get_user_by_email(email)
        logger.debug("Login attempt - Email: %s, User data: %s", email, user_data)
        if user_data:
            password_hash = user_data[3]
            logger.debug("Stored password hash: %s", password_hash)
            if check_password_hash(password_hash, password):
                user = User(id=user_data[0], username=user_data[1], email=user_data[2], is_admin=user_data[4])
                login_user(user, remember=True, force=True)
                session.permanent = True
                logger.debug("Login successful for user: %s, Session: %s", user.username, session)
                next_page = request.args.get('next')
                return redirect(next_page or url_for('home'))
            else:
                logger.debug("Password mismatch for email: %s", email)
                flash('Invalid email or password.')
        else:
            logger.debug("No user found for email: %s", email)
            flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))

@app.route('/home')
@login_required
def home():
    logger.debug("Home route hit. Current user authenticated: %s", current_user.is_authenticated)
    logger.debug("Session contents at home: %s", session)
    if not current_user.is_authenticated:
        logger.debug("User not authenticated, redirecting to login")
        return redirect(url_for('login'))

    conn = database.get_db_connection()
    cur = conn.cursor()

    search_query = request.args.get('query', '').strip()
    category_filter = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', "").strip()

    query = '''
        SELECT p.id, p.name, p.price, p.description, p.image, c.name 
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    '''
    params = []

    if search_query:
        query += " AND p.name ILIKE %s"
        params.append(f"%{search_query}%")

    if category_filter:
        query += " AND c.name = %s"
        params.append(category_filter)

    if min_price:
        query += " AND p.price >= %s"
        params.append(float(min_price))
    if max_price:
        query += " AND p.price <= %s"
        params.append(float(max_price))

    cur.execute(query, params)
    products = cur.fetchall()

    cur.execute('SELECT * FROM categories;')
    categories = cur.fetchall()

    # Fetch average ratings for all products
    avg_ratings = {}
    for product in products:
        cur.execute('''
            SELECT AVG(rating) FROM reviews WHERE product_id = %s
        ''', (product[0],))
        result = cur.fetchone()
        avg_ratings[product[0]] = round(result[0], 1) if result[0] else 0

    cur.close()
    conn.close()

    return render_template('home.html', products=products, categories=categories, 
                         search_query=search_query, category_filter=category_filter, 
                         min_price=min_price, max_price=max_price, avg_ratings=avg_ratings)

@app.route('/product/<int:product_id>')
def product(product_id):
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT p.id, p.name, p.price, p.description, p.image, 
               p.remaining_quantity, p.initial_quantity, c.id, c.name 
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.id = %s;
    ''', (product_id,))
    product = cur.fetchone()
    
    cur.execute('''
        SELECT r.rating, r.comment, u.username, r.created_at 
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = %s
        ORDER BY r.created_at DESC;
    ''', (product_id,))
    reviews = cur.fetchall()
    
    avg_rating = 0
    if reviews:
        avg_rating = sum(review[0] for review in reviews) / len(reviews)
    
    related_products = []
    if product:
        cur.execute('''
            SELECT p.id, p.name, p.price, p.description, p.image 
            FROM products p
            WHERE p.category_id = %s AND p.id != %s
            LIMIT 4;
        ''', (product[7], product_id))
        related_products = cur.fetchall()
    
    cur.close()
    conn.close()
    
    if product:
        return render_template('product.html',
            product=product,
            reviews=reviews,
            avg_rating=avg_rating,
            related_products=related_products,
            show_quantity=current_user.is_authenticated and current_user.is_admin
        )
    else:
        flash('Product not found.')
        return redirect(url_for('home'))

@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def submit_review(product_id):
    rating = request.form.get('rating')
    comment = request.form.get('comment')

    if not rating or not comment:
        flash('Please provide a rating and comment.')
        return redirect(url_for('product', product_id=product_id))

    conn = database.get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute('''
            INSERT INTO reviews (product_id, user_id, rating, comment)
            VALUES (%s, %s, %s, %s);
        ''', (product_id, current_user.id, int(rating), comment))
        conn.commit()
        flash('Review submitted successfully!')
    except Exception as e:
        logger.debug(f"Error submitting review: {str(e)}")
        flash('An error occurred while submitting the review.')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('product', product_id=product_id))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.')
        return redirect(url_for('home'))

    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM categories;')
    categories = cur.fetchall()
    cur.close()
    conn.close()

    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        description = request.form.get('description')
        category_id = request.form.get('category')
        quantity = int(request.form.get('quantity', 10))
        image = request.files.get('image')
        image_url = 'uploads/default-product.png'  # Default image

        if not all([name, price, category_id]):
            flash('Name, Price, and Category are required.')
            return redirect(url_for('add_product'))

        if image and allowed_file(image.filename):
            # Generate a unique filename using timestamp and user ID
            filename = secure_filename(f"product_{name.replace(' ', '_')}_{int(time.time())}_{current_user.id}.jpg")
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            image.save(file_path)
            image_url = f"uploads/{filename}"

        try:
            conn = database.get_db_connection()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO products 
                (name, price, description, image, category_id, initial_quantity, remaining_quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (name, float(price), description, image_url, int(category_id), quantity, quantity))
            new_product_id = cur.fetchone()[0]
            conn.commit()
            flash('Product added successfully!')
            return redirect(url_for('product', product_id=new_product_id))
        except Exception as e:
            logger.debug(f"Error adding product: {str(e)}")
            flash('An error occurred while adding the product.')
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    return render_template('add_product.html', categories=categories)

@app.route('/add-to-cart/<int:product_id>', methods=['POST'])
@login_required
def add_to_cart(product_id):
    quantity = int(request.form.get('quantity', 1))

    conn = database.get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute('''
            SELECT id, quantity FROM cart_items 
            WHERE user_id = %s AND product_id = %s;
        ''', (current_user.id, product_id))
        cart_item = cur.fetchone()

        if cart_item:
            new_quantity = cart_item[1] + quantity
            cur.execute('''
                UPDATE cart_items 
                SET quantity = %s 
                WHERE id = %s;
            ''', (new_quantity, cart_item[0]))
        else:
            cur.execute('''
                INSERT INTO cart_items (user_id, product_id, quantity)
                VALUES (%s, %s, %s);
            ''', (current_user.id, product_id, quantity))

        conn.commit()
        flash('Product added to cart!')
    except Exception as e:
        logger.debug(f"Error adding to cart: {str(e)}")
        flash('An error occurred while adding the product to the cart.')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('cart'))

@app.route('/cart')
@login_required
def cart():
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    cur.execute('''
        SELECT ci.id, p.id, p.name, p.price, p.image, ci.quantity 
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.user_id = %s
    ''', (current_user.id,))
    cart_items = cur.fetchall()

    total_price = sum(item[3] * item[5] for item in cart_items) if cart_items else 0
    
    cur.close()
    conn.close()
    
    return render_template('cart.html', 
                         cart_items=cart_items, 
                         total_price=total_price)

@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    try:
        session['user_id'] = current_user.id
        logger.debug("Stored user_id: %s in session", session['user_id'])

        cur.execute('''
            SELECT p.id, c.quantity, p.remaining_quantity, p.price
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        ''', (current_user.id,))
        cart_items = cur.fetchall()

        if not cart_items:
            flash('Your cart is empty.')
            return redirect(url_for('cart'))

        for item in cart_items:
            if item[2] < item[1]:
                flash(f'Not enough stock for product ID {item[0]}')
                return redirect(url_for('cart'))

        total_price = sum(item[3] * item[1] for item in cart_items)

        cart_items_json = json.dumps([{
            'product_id': item[0],
            'quantity': item[1],
            'price': float(item[3])
        } for item in cart_items])

        cur.execute('''
            INSERT INTO pending_orders (user_id, total_amount, cart_items_json)
            VALUES (%s, %s, %s)
            RETURNING id
        ''', (current_user.id, total_price, cart_items_json))
        pending_order_id = cur.fetchone()[0]
        conn.commit()

        user_details = database.get_user_details(current_user.id)
        if not user_details:
            flash('Error retrieving user details.')
            return redirect(url_for('cart'))

        return_url = f"{PAYFAST_RETURN_URL}?custom_int1={current_user.id}"
        payfast_data = {
            'merchant_id': PAYFAST_MERCHANT_ID,
            'merchant_key': PAYFAST_MERCHANT_KEY,
            'return_url': return_url,
            'cancel_url': PAYFAST_CANCEL_URL,
            'notify_url': PAYFAST_NOTIFY_URL,
            'name_first': user_details[1],
            'email_address': user_details[2],
            'm_payment_id': str(pending_order_id),
            'amount': str(total_price),
            'item_name': 'BuyMo Order',
            'item_description': f'Order for {user_details[1]}',
            'custom_int1': current_user.id,
        }

        sorted_data = sorted(payfast_data.items())
        signature_string = '&'.join([f"{key}={value}" for key, value in sorted_data])
        payfast_url = f"{PAYFAST_URL}?{urlencode(payfast_data)}"
        return redirect(payfast_url)

    except Exception as e:
        conn.rollback()
        flash(f'Error preparing payment: {str(e)}', 'error')
        return redirect(url_for('cart'))
    finally:
        cur.close()
        conn.close()

@app.route('/payfast/return', methods=['GET'])
def payfast_return():
    logger.debug("PayFast return hit. Current user authenticated: %s", current_user.is_authenticated)
    logger.debug("Session contents: %s", session)

    user_id = request.args.get('custom_int1')
    logger.debug("Attempting to re-authenticate with user_id: %s", user_id)
    if user_id:
        try:
            user_data = database.get_user_by_id(int(user_id))
            if user_data:
                user = User(id=user_data[0], username=user_data[1], email=user_data[2], is_admin=user_data[4])
                login_user(user, remember=True, force=True)
                session.permanent = True
                session['user_id'] = user.id
                logger.debug("User re-authenticated successfully: %s", user.username)
                return redirect(url_for('home'))
        except ValueError:
            logger.debug("Invalid user_id format: %s", user_id)
    
    logger.debug("Authentication failed or user_id missing")
    flash('Session expired. Please log in again.')
    return redirect(url_for('login'))

@app.route('/payfast/notify', methods=['POST'])
def payfast_notify():
    logger.debug("PayFast ITN received: %s", request.form)

    if request.form.get('payment_status') == 'COMPLETE':
        pending_order_id = request.form.get('m_payment_id')
        user_id = int(request.form.get('custom_int1'))

        conn = database.get_db_connection()
        try:
            cur = conn.cursor()

            cur.execute('''
                SELECT user_id, total_amount, cart_items_json
                FROM pending_orders
                WHERE id = %s
            ''', (pending_order_id,))
            pending_order = cur.fetchone()

            if not pending_order or pending_order[0] != user_id:
                logger.debug("Invalid order or user mismatch")
                return "Invalid order", 400

            total_amount = pending_order[1]
            cart_items = json.loads(pending_order[2])

            for item in cart_items:
                cur.execute('''
                    SELECT remaining_quantity
                    FROM products
                    WHERE id = %s
                ''', (item['product_id'],))
                remaining = cur.fetchone()[0]
                if remaining < item['quantity']:
                    logger.debug(f"Not enough stock for product {item['product_id']}")
                    return "Stock unavailable", 400

            cur.execute('''
                INSERT INTO orders (user_id, total_amount)
                VALUES (%s, %s)
                RETURNING id
            ''', (user_id, total_amount))
            order_id = cur.fetchone()[0]

            for item in cart_items:
                cur.execute('''
                    INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
                    VALUES (%s, %s, %s, %s)
                ''', (order_id, item['product_id'], item['quantity'], item['price']))

            for item in cart_items:
                cur.execute('''
                    UPDATE products 
                    SET remaining_quantity = remaining_quantity - %s
                    WHERE id = %s
                ''', (item['quantity'], item['product_id']))

            cur.execute('''
                DELETE FROM cart_items 
                WHERE user_id = %s
            ''', (user_id,))

            cur.execute('''
                DELETE FROM pending_orders
                WHERE id = %s
            ''', (pending_order_id,))

            conn.commit()
            logger.debug("Order completed successfully")

        except Exception as e:
            conn.rollback()
            logger.debug(f"Error processing ITN: {str(e)}")
            return "Error", 500
        finally:
            conn.close()

    return "OK", 200

@app.route('/remove-from-cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        
        cur.execute('''
            DELETE FROM cart_items 
            WHERE id = %s AND user_id = %s
            RETURNING id
        ''', (item_id, current_user.id))
        
        if cur.fetchone():
            conn.commit()
            flash('Item removed from cart', 'success')
        else:
            flash('Item not found in your cart', 'error')
            
    except Exception as e:
        conn.rollback()
        flash(f'Error removing item: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('cart'))

@app.route('/update-cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    try:
        quantity = int(request.form['quantity'])
        if quantity < 1:
            return redirect(url_for('remove_from_cart', item_id=item_id))
            
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            UPDATE cart_items
            SET quantity = %s
            WHERE id = %s AND user_id = %s
            RETURNING quantity
        ''', (quantity, item_id, current_user.id))
        
        if cur.fetchone():
            conn.commit()
            flash('Cart updated successfully', 'success')
        else:
            flash('Item not found in your cart', 'error')
            
    except ValueError:
        flash('Please enter a valid quantity', 'error')
    except Exception as e:
        conn.rollback()
        flash(f'Error updating cart: {str(e)}', 'error')
    finally:
        if conn:
            conn.close()
    
    return redirect(url_for('cart'))

@app.route('/edit-product/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    if not current_user.is_admin:
        abort(403)
    
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM products WHERE id = %s', (product_id,))
        product = cur.fetchone()
        
        if not product:
            flash('Product not found')
            return redirect(url_for('home'))
            
        cur.execute('SELECT * FROM categories')
        categories = cur.fetchall()
        
        if request.method == 'POST':
            name = request.form['name']
            price = float(request.form['price'])
            description = request.form['description']
            category_id = int(request.form['category'])
            image_url = product[4]  # Keep existing image

            cur.execute('''
                UPDATE products 
                SET name = %s, price = %s, description = %s, image = %s, category_id = %s
                WHERE id = %s
            ''', (name, price, description, image_url, category_id, product_id))
            
            conn.commit()
            flash('Product updated successfully!')
            return redirect(url_for('product', product_id=product_id))
        
        return render_template('edit_product.html', 
                           product=product, 
                           categories=categories)
    
    except Exception as e:
        conn.rollback()
        flash(f'Error updating product: {str(e)}', 'error')
        return redirect(url_for('edit_product', product_id=product_id))
    
    finally:
        conn.close()

@app.route('/delete-product/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    if not current_user.is_admin:
        abort(403)
    
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM cart_items WHERE product_id = %s", (product_id,))
        cur.execute("DELETE FROM reviews WHERE product_id = %s", (product_id,))
        cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
        conn.commit()
        flash('Product deleted successfully')
    except Exception as e:
        conn.rollback()
        flash(f'Error deleting product: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('home'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = get_user_details(current_user.id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        profile_image = user[4]  # Keep existing image if no new upload
        
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"user_{current_user.id}.{file.filename.rsplit('.', 1)[1].lower()}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER_PROFILES'], filename)
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                file.save(file_path)
                profile_image = f"uploads/profiles/{filename}"
                # Note: Render's ephemeral filesystem means this file may not persist across redeploys

        if update_user_profile(current_user.id, username, email, profile_image):
            flash('Profile updated successfully!', 'success')
        else:
            flash('Error updating profile', 'danger')
    
    return render_template('profile.html', user=user)

@app.route('/change-password', methods=['POST'])
@login_required
def change_password():
    conn = None
    try:
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form.get('confirm_password', '')

        if not all([current_password, new_password, confirm_password]):
            flash("All fields are required", "error")
            return redirect(url_for('profile'))
            
        if new_password != confirm_password:
            flash("New passwords don't match", "error")
            return redirect(url_for('profile'))
            
        if len(new_password) < 8:
            flash("Password must be at least 8 characters", "error")
            return redirect(url_for('profile'))

        user = database.get_user_by_id(current_user.id)
        if not user:
            flash("User not found", "error")
            return redirect(url_for('profile'))
            
        if not check_password_hash(user[3], current_password):
            flash("Current password is incorrect", "error")
            return redirect(url_for('profile'))

        conn = database.get_db_connection()
        cur = conn.cursor()
        hashed_pw = generate_password_hash(new_password)
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (hashed_pw, current_user.id)
        )
        conn.commit()
        logger.debug("Password updated successfully for user ID: %s", current_user.id)
        flash("Password updated successfully!", "success")

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Error updating password: {0}".format(str(e)))
        flash(f"Error updating password: {str(e)}", "error")
    finally:
        if conn:
            conn.close()
            
    return redirect(url_for('profile'))

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.remember_cookie_duration = timedelta(days=7)
login_manager.session_protection = 'strong'

class User(UserMixin):
    def __init__(self, id, username, email, is_admin):
        self.id = id
        self.username = username
        self.email = email
        self.is_admin = is_admin

@login_manager.user_loader
def load_user(user_id):
    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s;', (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    if user_data:
        return User(id=user_data[0],
                  username=user_data[1],
                  email=user_data[2],
                  is_admin=user_data[4])
    return None

@app.route('/orders')
@login_required
def orders():
    logger.debug("Accessing orders route. User authenticated: %s, User ID: %s", current_user.is_authenticated, current_user.id)
    conn = database.get_db_connection()
    cur = conn.cursor()

    # Fetch completed orders
    cur.execute('''
        SELECT o.id, o.total_amount, o.order_date
        FROM orders o
        WHERE o.user_id = %s
        ORDER BY o.order_date DESC;
    ''', (current_user.id,))
    completed_orders = cur.fetchall()

    order_history = []
    for order in completed_orders:
        order_id = order[0]
        cur.execute('''
            SELECT p.name, p.image, oi.quantity, oi.price_at_purchase
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s;
        ''', (order_id,))
        order_items = cur.fetchall()
        order_history.append({
            'id': order_id,
            'total_amount': float(order[1]),  # Convert Decimal to float for template
            'order_date': order[2],
            'order_items': [{'name': item[0], 'image': item[1], 'quantity': item[2], 'price_at_purchase': float(item[3])} for item in order_items]
        })

    cur.close()
    conn.close()

    logger.debug("Rendering orders.html with order_history: %s", order_history)
    return render_template('orders.html', orders=order_history)

if __name__ == '__main__':
    app.run(debug=True, port=5000)  # Ensure port is set to 5000 for Render