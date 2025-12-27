from flask import Flask, render_template, request, redirect, url_for, flash, abort, session, jsonify
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
import time
import cloudinary
import cloudinary.uploader
import random
import string

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

@app.template_filter('resolve_image')
def resolve_image(image_path):
    if not image_path:
        return url_for('static', filename='uploads/default-product.png')
    if image_path.startswith('http') or image_path.startswith('https'):
        return image_path
    return url_for('static', filename=image_path)

# Configure upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['UPLOAD_FOLDER_PROFILES'] = 'static/uploads/profiles'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024  # 2MB

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def calculate_profile_completion(user):
    """Calculate profile completion percentage"""
    completion = 0
    total_fields = 3
    
    # Username (always present)
    if user[1]:
        completion += 1
    
    # Email (always present)
    if user[2]:
        completion += 1
    
    # Profile image
    if user[4] and user[4] != 'uploads/profiles/default-profile.png':
        completion += 1
    
    return int((completion / total_fields) * 100)

def generate_tracking_number():
    """Generate a unique tracking number in format: BM-YYYYMMDD-XXXXX"""
    from datetime import datetime
    date_str = datetime.now().strftime('%Y%m%d')
    random_str = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
    return f"BM-{date_str}-{random_str}"

@app.context_processor
def inject_cart_count():
    """Make cart count available to all templates with caching"""
    cart_count = 0
    if current_user.is_authenticated:
        # Use session cache to avoid DB query on every request
        cache_key = f'cart_count_{current_user.id}'
        
        # Check if we have a cached value in session
        if cache_key in session:
            cart_count = session[cache_key]
        else:
            # Only query DB if not cached
            try:
                conn = database.get_db_connection()
                cur = conn.cursor()
                cur.execute('SELECT COUNT(*) FROM cart_items WHERE user_id = %s', (current_user.id,))
                cart_count = cur.fetchone()[0]
                cur.close()
                conn.close()
                # Cache for this session
                session[cache_key] = cart_count
            except Exception as e:
                logger.error(f"Error fetching cart count: {str(e)}")
                cart_count = 0
    return dict(cart_count=cart_count)



# Routes
@app.route('/')
def index():
    """Landing page with featured products and categories"""
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        # Get featured products (latest 8 products)
        try:
            cur.execute('''
                SELECT p.id, p.name, p.price, p.description, p.image, c.name, p.remaining_quantity
                FROM products p
                JOIN categories c ON p.category_id = c.id
                ORDER BY p.id DESC
                LIMIT 8
            ''')
            featured_products = cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching featured products: {str(e)}")
            featured_products = []
        
        # Get all categories
        try:
            cur.execute('SELECT * FROM categories ORDER BY name')
            categories = cur.fetchall()
        except Exception as e:
            logger.error(f"Error fetching categories: {str(e)}")
            categories = []
        
        # Get stats for social proof
        try:
            cur.execute('SELECT COUNT(*) FROM products')
            total_products = cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error fetching product count: {str(e)}")
            total_products = 0
        
        try:
            cur.execute('SELECT COUNT(*) FROM orders')
            total_orders = cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error fetching order count: {str(e)}")
            total_orders = 0
        
        try:
            cur.execute('SELECT COUNT(*) FROM users')
            total_customers = cur.fetchone()[0]
        except Exception as e:
            logger.error(f"Error fetching user count: {str(e)}")
            total_customers = 0
        
        cur.close()
        conn.close()
        
        return render_template('landing.html', 
                             featured_products=featured_products,
                             categories=categories,
                             total_products=total_products,
                             total_orders=total_orders,
                             total_customers=total_customers)
    except Exception as e:
        logger.error(f"Critical error in landing page: {str(e)}")
        # Fallback: redirect to signup if landing page fails
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
            flash('Email already registered. Please login.', 'warning')
            return redirect(url_for('login'))

        database.create_user(username, email, password)
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user_data = database.get_user_by_email(email)
        if user_data:
            password_hash = user_data[3]
            if check_password_hash(password_hash, password):
                user = User(id=user_data[0], username=user_data[1], email=user_data[2], is_admin=user_data[4])
                login_user(user, remember=True, force=True)
                session.permanent = True
                flash(f'Welcome back, {user.username}!', 'success')
                next_page = request.args.get('next')
                return redirect(next_page or url_for('home'))
            else:
                flash('Invalid email or password.', 'error')
        else:
            flash('Invalid email or password.', 'error')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'success')
    return redirect(url_for('index'))

@app.route('/home')
@login_required
def home():
    if not current_user.is_authenticated:
        return redirect(url_for('login'))

    conn = database.get_db_connection()
    cur = conn.cursor()

    search_query = request.args.get('query', '').strip()
    category_filter = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', "").strip()

    # Check if is_active column exists
    cur.execute("""
        SELECT column_name 
        FROM information_schema.columns 
        WHERE table_name='products' AND column_name='is_active'
    """)
    has_is_active = cur.fetchone() is not None
    
    if has_is_active:
        query = '''
            SELECT p.id, p.name, p.price, p.description, p.image, c.name, p.remaining_quantity
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE COALESCE(p.is_active, true) = true
        '''
    else:
        query = '''
            SELECT p.id, p.name, p.price, p.description, p.image, c.name, p.remaining_quantity
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

    # Fetch average ratings and review counts for all products
    avg_ratings = {}
    review_counts = {}
    for product in products:
        cur.execute('''
            SELECT AVG(rating), COUNT(*) FROM reviews WHERE product_id = %s
        ''', (product[0],))
        result = cur.fetchone()
        avg_ratings[product[0]] = round(result[0], 1) if result[0] else 0
        review_counts[product[0]] = result[1] if result[1] else 0

    cur.close()
    conn.close()

    return render_template('home.html', products=products, categories=categories, 
                         search_query=search_query, category_filter=category_filter, 
                         min_price=min_price, max_price=max_price, 
                         avg_ratings=avg_ratings, review_counts=review_counts)

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
        flash('Product not found.', 'error')
        return redirect(url_for('home'))

@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def submit_review(product_id):
    rating = request.form.get('rating')
    comment = request.form.get('comment')

    if not rating or not comment:
        flash('Please provide a rating and comment.', 'warning')
        return redirect(url_for('product', product_id=product_id))

    conn = database.get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute('''
            INSERT INTO reviews (product_id, user_id, rating, comment)
            VALUES (%s, %s, %s, %s);
        ''', (product_id, current_user.id, int(rating), comment))
        conn.commit()
        flash('Review submitted successfully!', 'success')
    except Exception as e:
        logger.error(f"Error submitting review: {str(e)}")
        flash('An error occurred while submitting the review.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('product', product_id=product_id))

@app.route('/add', methods=['GET', 'POST'])
@login_required
def add_product():
    if not current_user.is_admin:
        flash('You do not have permission to access this page.', 'error')
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
            flash('Name, Price, and Category are required.', 'warning')
            return redirect(url_for('add_product'))

        if image and image.filename and allowed_file(image.filename):
            if os.getenv('CLOUDINARY_CLOUD_NAME'):
                try:
                    cloudinary.config(
                        cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
                        api_key = os.getenv('CLOUDINARY_API_KEY'),
                        api_secret = os.getenv('CLOUDINARY_API_SECRET')
                    )
                    upload_result = cloudinary.uploader.upload(image)
                    image_url = upload_result['secure_url']
                    logger.info(f"Image uploaded to Cloudinary: {image_url}")
                except Exception as e:
                    logger.error(f"Cloudinary upload failed: {str(e)}")
                    # Fallback to local if Cloudinary fails? Or just fail?
                    # Let's try to fallback or just warn.
                    flash('Cloudinary upload failed, falling back to local storage (ephemeral).', 'warning')
                    ext = image.filename.rsplit('.', 1)[1].lower()
                    filename = secure_filename(f"product_{name.replace(' ', '_')}_{int(time.time())}_{current_user.id}.{ext}")
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                    image.save(file_path)
                    image_url = f"uploads/{filename}"
            else:
                # Generate a unique filename preserving original extension
                ext = image.filename.rsplit('.', 1)[1].lower()
                filename = secure_filename(f"product_{name.replace(' ', '_')}_{int(time.time())}_{current_user.id}.{ext}")
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                # Ensure upload directory exists
                os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
                
                image.save(file_path)
                image_url = f"uploads/{filename}"
                logger.info(f"Image saved to: {file_path}")


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
            flash('Product added successfully!', 'success')
            return redirect(url_for('product', product_id=new_product_id))
        except Exception as e:
            logger.error(f"Error adding product: {str(e)}")
            flash('An error occurred while adding the product.', 'error')
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
        
        # Clear cart count cache
        cache_key = f'cart_count_{current_user.id}'
        session.pop(cache_key, None)
        
        flash('Product added to cart!', 'success')
    except Exception as e:
        logger.error(f"Error adding to cart: {str(e)}")
        flash('An error occurred while adding the product to the cart.', 'error')
    finally:
        cur.close()
        conn.close()

    return redirect(url_for('cart'))

@app.route('/api/cart-count')
@login_required
def api_cart_count():
    """API endpoint to get current cart item count"""
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT COUNT(*) FROM cart_items WHERE user_id = %s', (current_user.id,))
        count = cur.fetchone()[0]
        cur.close()
        conn.close()
        return jsonify({'count': count})
    except Exception as e:
        logger.error(f"Error fetching cart count: {str(e)}")
        return jsonify({'count': 0})

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

@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    # GET: Show checkout form
    if request.method == 'GET':
        cur.execute('''
            SELECT ci.id, p.id, p.name, p.price, p.image, ci.quantity 
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            WHERE ci.user_id = %s
        ''', (current_user.id,))
        cart_items = cur.fetchall()
        
        if not cart_items:
            flash('Your cart is empty.', 'warning')
            cur.close()
            conn.close()
            return redirect(url_for('cart'))
        
        subtotal = float(sum(item[3] * item[5] for item in cart_items))
        delivery_fee = 50.00 if subtotal < 1000 else 0.00
        
        # Get last order for pre-filling - use a fresh connection to avoid cache
        last_order = None
        try:
            # Try to get last order, but don't fail if columns don't exist yet
            cur.execute('''
                SELECT full_name, phone, street_address, suburb, city, province, postal_code
                FROM orders
                WHERE user_id = %s AND delivery_method = 'delivery'
                ORDER BY order_date DESC
                LIMIT 1
            ''', (current_user.id,))
            last_order_data = cur.fetchone()
            if last_order_data:
                last_order = {
                    'full_name': last_order_data[0],
                    'phone': last_order_data[1],
                    'street_address': last_order_data[2],
                    'suburb': last_order_data[3],
                    'city': last_order_data[4],
                    'province': last_order_data[5],
                    'postal_code': last_order_data[6]
                }
        except Exception as e:
            # If query fails (columns don't exist), just skip pre-filling
            logger.warning(f"Could not fetch last order: {str(e)}")
            last_order = None
        
        cur.close()
        conn.close()
        
        from datetime import date
        return render_template('checkout.html', 
                             cart_items=cart_items,
                             subtotal=subtotal,
                             delivery_fee=delivery_fee,
                             last_order=last_order,
                             today=date.today().isoformat())
    
    # POST: Process checkout and redirect to PayFast
    try:
        session['user_id'] = current_user.id

        cur.execute('''
            SELECT p.id, c.quantity, p.remaining_quantity, p.price
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        ''', (current_user.id,))
        cart_items = cur.fetchall()

        if not cart_items:
            flash('Your cart is empty.', 'warning')
            return redirect(url_for('cart'))

        for item in cart_items:
            if item[2] < item[1]:
                flash(f'Not enough stock for product ID {item[0]}', 'error')
                return redirect(url_for('cart'))

        subtotal = float(sum(item[3] * item[1] for item in cart_items))
        
        # Get delivery info from form
        delivery_method = request.form.get('delivery_method', 'delivery')
        full_name = request.form.get('full_name')
        phone = request.form.get('phone')
        
        # Calculate delivery fee
        if delivery_method == 'delivery':
            delivery_fee = 50.00 if subtotal < 1000 else 0.00
            street_address = request.form.get('street_address')
            suburb = request.form.get('suburb')
            city = request.form.get('city')
            province = request.form.get('province')
            postal_code = request.form.get('postal_code')
            pickup_date = None
        else:
            delivery_fee = 0.00
            street_address = None
            suburb = None
            city = None
            province = None
            postal_code = None
            pickup_date = request.form.get('pickup_date')
        
        total_price = subtotal + delivery_fee

        # Prepare delivery info JSON
        delivery_info = {
            'delivery_method': delivery_method,
            'full_name': full_name,
            'phone': phone,
            'street_address': street_address,
            'suburb': suburb,
            'city': city,
            'province': province,
            'postal_code': postal_code,
            'pickup_date': pickup_date,
            'delivery_fee': float(delivery_fee)
        }
        
        cart_items_json = json.dumps([{
            'product_id': item[0],
            'quantity': item[1],
            'price': float(item[3])
        } for item in cart_items])

        delivery_info_json = json.dumps(delivery_info)
        
        cur.execute('''
            INSERT INTO pending_orders (user_id, total_amount, cart_items_json, delivery_info_json)
            VALUES (%s, %s, %s, %s)
            RETURNING id
        ''', (current_user.id, total_price, cart_items_json, delivery_info_json))
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
    user_id = request.args.get('custom_int1')
    if user_id:
        try:
            user_data = database.get_user_by_id(int(user_id))
            if user_data:
                user = User(id=user_data[0], username=user_data[1], email=user_data[2], is_admin=user_data[4])
                login_user(user, remember=True, force=True)
                session.permanent = True
                session['user_id'] = user.id
                flash('Order placed successfully! Check your orders page for details.', 'success')
                return redirect(url_for('orders'))
        except ValueError:
            pass
    
    flash('Session expired. Please log in again.')
    return redirect(url_for('login'))

@app.route('/payfast/notify', methods=['POST'])
def payfast_notify():
    logger.info("PayFast ITN received")

    if request.form.get('payment_status') == 'COMPLETE':
        pending_order_id = request.form.get('m_payment_id')
        user_id = int(request.form.get('custom_int1'))

        conn = database.get_db_connection()
        try:
            cur = conn.cursor()

            cur.execute('''
                SELECT user_id, total_amount, cart_items_json, delivery_info_json
                FROM pending_orders
                WHERE id = %s
            ''', (pending_order_id,))
            pending_order = cur.fetchone()

            if not pending_order or pending_order[0] != user_id:
                logger.warning("Invalid order or user mismatch")
                return "Invalid order", 400

            total_amount = pending_order[1]
            cart_items = json.loads(pending_order[2])
            delivery_info = json.loads(pending_order[3]) if pending_order[3] else {}

            for item in cart_items:
                cur.execute('''
                    SELECT remaining_quantity
                    FROM products
                    WHERE id = %s
                ''', (item['product_id'],))
                remaining = cur.fetchone()[0]
                if remaining < item['quantity']:
                    logger.warning(f"Not enough stock for product {item['product_id']}")
                    return "Stock unavailable", 400

            # delivery_info already loaded from pending_orders table above
            
            # Generate unique tracking number
            tracking_number = generate_tracking_number()
            
            cur.execute('''
                INSERT INTO orders (
                    user_id, tracking_number, total_amount, delivery_method, full_name, phone,
                    street_address, suburb, city, province, postal_code,
                    delivery_fee, pickup_date, status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            ''', (
                user_id,
                tracking_number,
                total_amount,
                delivery_info.get('delivery_method', 'delivery'),
                delivery_info.get('full_name'),
                delivery_info.get('phone'),
                delivery_info.get('street_address'),
                delivery_info.get('suburb'),
                delivery_info.get('city'),
                delivery_info.get('province'),
                delivery_info.get('postal_code'),
                delivery_info.get('delivery_fee', 0),
                delivery_info.get('pickup_date'),
                'processing'
            ))
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
            logger.info("Order completed successfully")

        except Exception as e:
            conn.rollback()
            logger.error(f"Error processing ITN: {str(e)}")
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
            
            # Clear cart count cache
            cache_key = f'cart_count_{current_user.id}'
            session.pop(cache_key, None)
            
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
            flash('Product updated successfully!', 'success')
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
    
    force_delete = request.form.get('force_delete') == 'true'
    
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        
        if force_delete:
            # Force delete - remove from order_items first, then product
            cur.execute("DELETE FROM cart_items WHERE product_id = %s", (product_id,))
            cur.execute("DELETE FROM reviews WHERE product_id = %s", (product_id,))
            cur.execute("DELETE FROM order_items WHERE product_id = %s", (product_id,))
            cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
            conn.commit()
            flash('Product permanently deleted!', 'success')
        else:
            # Regular delete - check for orders first
            cur.execute("SELECT COUNT(*) FROM order_items WHERE product_id = %s", (product_id,))
            order_count = cur.fetchone()[0]
            
            if order_count > 0:
                flash(f'Product has {order_count} order(s). Use "Force Delete" to remove permanently.', 'warning')
            else:
                cur.execute("DELETE FROM cart_items WHERE product_id = %s", (product_id,))
                cur.execute("DELETE FROM reviews WHERE product_id = %s", (product_id,))
                cur.execute("DELETE FROM products WHERE id = %s", (product_id,))
                conn.commit()
                flash('Product deleted successfully!', 'success')
            
    except Exception as e:
        conn.rollback()
        logger.error(f'Error deleting product: {str(e)}')
        flash(f'Error: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('admin_products'))

@app.route('/toggle-product/<int:product_id>', methods=['POST'])
@login_required
def toggle_product(product_id):
    if not current_user.is_admin:
        abort(403)
    
    # Toggle functionality disabled - is_active column doesn't exist in current schema
    flash('Product toggle feature temporarily disabled.', 'info')
    return redirect(url_for('admin_products'))

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
            if file and file.filename != '' and allowed_file(file.filename):
                if os.getenv('CLOUDINARY_CLOUD_NAME'):
                    try:
                        cloudinary.config(
                            cloud_name = os.getenv('CLOUDINARY_CLOUD_NAME'),
                            api_key = os.getenv('CLOUDINARY_API_KEY'),
                            api_secret = os.getenv('CLOUDINARY_API_SECRET')
                        )
                        upload_result = cloudinary.uploader.upload(file)
                        profile_image = upload_result['secure_url']
                        logger.info(f"Profile image uploaded to Cloudinary: {profile_image}")
                    except Exception as e:
                        logger.error(f"Cloudinary upload failed: {str(e)}")
                        flash('Image upload failed. Using local storage.', 'warning')
                        filename = secure_filename(f"user_{current_user.id}_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}")
                        file_path = os.path.join(app.config['UPLOAD_FOLDER_PROFILES'], filename)
                        os.makedirs(os.path.dirname(file_path), exist_ok=True)
                        file.save(file_path)
                        profile_image = f"uploads/profiles/{filename}"
                else:
                    filename = secure_filename(f"user_{current_user.id}_{int(time.time())}.{file.filename.rsplit('.', 1)[1].lower()}")
                    file_path = os.path.join(app.config['UPLOAD_FOLDER_PROFILES'], filename)
                    os.makedirs(os.path.dirname(file_path), exist_ok=True)
                    file.save(file_path)
                    profile_image = f"uploads/profiles/{filename}"
                    logger.info(f"Profile image saved: {profile_image}")


        if update_user_profile(current_user.id, username, email, profile_image):
            flash('Profile updated successfully!', 'success')
        else:
            flash('Error updating profile', 'error')
    
    # Calculate profile completion
    completion = calculate_profile_completion(user)
    
    # Fetch user orders
    orders = []
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute('''
            SELECT id, total_amount, status, order_date, tracking_number 
            FROM orders 
            WHERE user_id = %s 
            ORDER BY order_date DESC
        ''', (current_user.id,))
        orders = cur.fetchall()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error fetching user orders: {e}")

    return render_template('profile.html', user=user, completion=completion, orders=orders)

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
        hashed_pw = generate_password_hash(new_password, method='pbkdf2:sha256', salt_length=16)
        cur.execute(
            "UPDATE users SET password_hash = %s WHERE id = %s",
            (hashed_pw, current_user.id)
        )
        conn.commit()
        cur.close()
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
    # Get a fresh connection to avoid schema cache issues
    conn = database.get_db_connection()
    conn.set_session(autocommit=True)  # Force new transaction
    cur = conn.cursor()

    # Fetch completed orders with delivery info and status
    try:
        cur.execute('''
            SELECT o.id, o.total_amount, o.order_date, o.status, o.delivery_method,
                   o.full_name, o.phone, o.street_address, o.suburb, o.city, 
                   o.province, o.postal_code, o.delivery_fee, o.pickup_date
            FROM orders o
            WHERE o.user_id = %s
            ORDER BY o.order_date DESC;
        ''', (current_user.id,))
        completed_orders = cur.fetchall()
    except Exception as e:
        # If columns don't exist yet, rollback and try basic query
        logger.error(f"Error fetching orders: {str(e)}")
        conn.rollback()  # IMPORTANT: Rollback the failed transaction
        cur.execute('''
            SELECT o.id, o.total_amount, o.order_date
            FROM orders o
            WHERE o.user_id = %s
            ORDER BY o.order_date DESC;
        ''', (current_user.id,))
        basic_orders = cur.fetchall()
        # Return basic order view with default values
        order_history = []
        for order in basic_orders:
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
                'total_amount': float(order[1]),
                'order_date': order[2],
                'status': 'processing',
                'delivery_method': 'delivery',
                'full_name': 'N/A',
                'phone': 'N/A',
                'street_address': 'Address not available',
                'suburb': '',
                'city': '',
                'province': '',
                'postal_code': '',
                'delivery_fee': 0,
                'pickup_date': None,
                'order_items': [{'name': item[0], 'image': item[1], 'quantity': item[2], 'price_at_purchase': float(item[3])} for item in order_items]
            })
        cur.close()
        conn.close()
        return render_template('orders.html', orders=order_history)

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
            'total_amount': float(order[1]),
            'order_date': order[2],
            'status': order[3] or 'processing',
            'delivery_method': order[4] or 'delivery',
            'full_name': order[5],
            'phone': order[6],
            'street_address': order[7],
            'suburb': order[8],
            'city': order[9],
            'province': order[10],
            'postal_code': order[11],
            'delivery_fee': float(order[12]) if order[12] else 0,
            'pickup_date': order[13],
            'order_items': [{'name': item[0], 'image': item[1], 'quantity': item[2], 'price_at_purchase': float(item[3])} for item in order_items]
        })

    cur.close()
    conn.close()

    return render_template('orders.html', orders=order_history)

@app.route('/admin/products')
@login_required
def admin_products():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'error')
        return redirect(url_for('home'))
    
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    # Fetch all products with order count and active status
    cur.execute('''
        SELECT p.id, p.name, p.price, p.remaining_quantity, p.image,
               COUNT(DISTINCT oi.order_id) as order_count,
               true as is_active
        FROM products p
        LEFT JOIN order_items oi ON p.id = oi.product_id
        GROUP BY p.id, p.name, p.price, p.remaining_quantity, p.image
        ORDER BY p.id DESC
    ''')
    products = cur.fetchall()
    
    products_list = []
    for product in products:
        products_list.append({
            'id': product[0],
            'name': product[1],
            'price': float(product[2]),
            'stock': product[3],
            'image': product[4],
            'order_count': product[5],
            'is_active': product[6] if len(product) > 6 else True
        })
    
    cur.close()
    conn.close()
    
    return render_template('admin_products.html', products=products_list)

@app.route('/admin/orders')
@login_required
def admin_orders():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'error')
        return redirect(url_for('home'))
    
    # Get a fresh connection
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    # Fetch all orders with user info - use simple query that works
    cur.execute('''
        SELECT o.id, o.total_amount, o.order_date, 
               COALESCE(o.status, 'processing') as status,
               COALESCE(o.delivery_method, 'delivery') as delivery_method,
               u.username, u.email
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.order_date DESC
    ''')
    all_orders = cur.fetchall()
    
    orders_list = []
    for order in all_orders:
        orders_list.append({
            'id': order[0],
            'total_amount': float(order[1]),
            'order_date': order[2],
            'status': order[3] or 'processing',
            'delivery_method': order[4] or 'delivery',
            'customer_name': order[5],
            'customer_email': order[6]
        })
    
    cur.close()
    conn.close()
    
    return render_template('admin_orders.html', orders=orders_list)

@app.route('/admin/order/<int:order_id>/update-status', methods=['POST'])
@login_required
def admin_update_order_status(order_id):
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'error')
        return redirect(url_for('home'))
    
    new_status = request.form.get('status')
    
    if new_status not in ['processing', 'shipped', 'delivered']:
        flash('Invalid status.', 'error')
        return redirect(url_for('admin_orders'))
    
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    try:
        cur.execute('''
            UPDATE orders 
            SET status = %s, status_updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
        ''', (new_status, order_id))
        conn.commit()
        flash(f'Order #{order_id} status updated to {new_status.title()}!', 'success')
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating order status: {str(e)}")
        flash('Error updating order status.', 'error')
    finally:
        cur.close()
        conn.close()
    
    return redirect(url_for('admin_orders'))

@app.route('/admin/order/<int:order_id>/details')
@login_required
def admin_order_details(order_id):
    if not current_user.is_admin:
        return jsonify({'error': 'Access denied'}), 403
    
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    try:
        # Get order details
        cur.execute('''
            SELECT o.id, o.total_amount, o.order_date, 
                   COALESCE(o.status, 'processing') as status,
                   COALESCE(o.delivery_method, 'delivery') as delivery_method,
                   o.full_name, o.phone, o.street_address, o.suburb, o.city,
                   o.province, o.postal_code, o.delivery_fee, o.pickup_date,
                   u.username, u.email
            FROM orders o
            JOIN users u ON o.user_id = u.id
            WHERE o.id = %s
        ''', (order_id,))
        order = cur.fetchone()
        
        if not order:
            return jsonify({'error': 'Order not found'}), 404
        
        # Get order items
        cur.execute('''
            SELECT p.name, p.image, oi.quantity, oi.price_at_purchase
            FROM order_items oi
            JOIN products p ON oi.product_id = p.id
            WHERE oi.order_id = %s
        ''', (order_id,))
        items = cur.fetchall()
        
        order_data = {
            'id': order[0],
            'total_amount': float(order[1]),
            'order_date': order[2].strftime('%B %d, %Y at %I:%M %p'),
            'status': order[3],
            'delivery_method': order[4],
            'full_name': order[5],
            'phone': order[6],
            'street_address': order[7],
            'suburb': order[8],
            'city': order[9],
            'province': order[10],
            'postal_code': order[11],
            'delivery_fee': float(order[12]) if order[12] else 0,
            'pickup_date': order[13].strftime('%B %d, %Y') if order[13] else None,
            'customer_name': order[14],
            'customer_email': order[15],
            'items': [{
                'name': item[0],
                'image': item[1],
                'quantity': item[2],
                'price': float(item[3])
            } for item in items]
        }
        
        return jsonify(order_data)
        
    except Exception as e:
        logger.error(f"Error fetching order details: {str(e)}")
        return jsonify({'error': 'Failed to fetch order details'}), 500
    finally:
        cur.close()
        conn.close()

@app.route('/admin/migrate-database', methods=['GET', 'POST'])
@login_required
def migrate_database():
    if not current_user.is_admin:
        flash('Access denied. Admin only.', 'error')
        return redirect(url_for('home'))
    
    if request.method == 'POST':
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        try:
            results = []
            
            # First, add delivery_info_json to pending_orders table
            try:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='pending_orders' AND column_name='delivery_info_json'
                """)
                if cur.fetchone() is None:
                    cur.execute("ALTER TABLE pending_orders ADD COLUMN delivery_info_json TEXT")
                    conn.commit()
                    results.append("✓ Added: pending_orders.delivery_info_json")
                else:
                    results.append("○ Exists: pending_orders.delivery_info_json")
            except Exception as e:
                conn.rollback()
                results.append(f"✗ Error: pending_orders.delivery_info_json - {str(e)}")
            
            # Add is_active to products table
            try:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='products' AND column_name='is_active'
                """)
                if cur.fetchone() is None:
                    cur.execute("ALTER TABLE products ADD COLUMN is_active BOOLEAN DEFAULT true")
                    conn.commit()
                    results.append("✓ Added: products.is_active")
                else:
                    results.append("○ Exists: products.is_active")
            except Exception as e:
                conn.rollback()
                results.append(f"✗ Error: products.is_active - {str(e)}")
            
            # Add new columns to orders table
            columns_to_add = [
                ("delivery_method", "VARCHAR(20) DEFAULT 'delivery'"),
                ("full_name", "VARCHAR(100)"),
                ("phone", "VARCHAR(20)"),
                ("street_address", "TEXT"),
                ("suburb", "VARCHAR(100)"),
                ("city", "VARCHAR(100)"),
                ("province", "VARCHAR(50)"),
                ("postal_code", "VARCHAR(10)"),
                ("delivery_fee", "DECIMAL(10, 2) DEFAULT 50.00"),
                ("status", "VARCHAR(50) DEFAULT 'processing'"),
                ("status_updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
                ("pickup_date", "DATE")
            ]
            for col_name, col_type in columns_to_add:
                try:
                    # Check if column exists
                    cur.execute(f"""
                        SELECT column_name 
                        FROM information_schema.columns 
                        WHERE table_name='orders' AND column_name='{col_name}'
                    """)
                    
                    if cur.fetchone() is None:
                        cur.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
                        conn.commit()
                        results.append(f"✓ Added: {col_name}")
                    else:
                        results.append(f"○ Exists: {col_name}")
                except Exception as e:
                    conn.rollback()
                    results.append(f"✗ Error: {col_name} - {str(e)}")
            
            flash(f"Migration complete! {len([r for r in results if '✓' in r])} columns added.", 'success')
            return render_template('admin_migrate.html', results=results, migrated=True)
            
        except Exception as e:
            conn.rollback()
            flash(f"Migration failed: {str(e)}", 'error')
            return render_template('admin_migrate.html', results=[f"Error: {str(e)}"], migrated=False)
        finally:
            cur.close()
            conn.close()
    
    return render_template('admin_migrate.html', results=None, migrated=False)

@app.route('/emergency-reset-admin')
def emergency_reset_admin():
    """Temporary route to reset admin password in production"""
    # Simple security key check to prevent random access
    if request.args.get('key') != 'SecureReset2025':
        return "Access Denied", 403
        
    email = "admin@gmail.com"
    new_password = "12345678"
    
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        # Hash the new password
        password_hash = generate_password_hash(
            new_password,
            method='pbkdf2:sha256',
            salt_length=16
        )
        
        # Update the user
        cur.execute("UPDATE users SET password_hash = %s WHERE email = %s", (password_hash, email))
        
        if cur.rowcount == 0:
            result = "User admin@gmail.com not found!"
        else:
            conn.commit()
            result = f"SUCCESS: Password for {email} has been reset to {new_password}"
            
        cur.close()
        conn.close()
        return result
        
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == '__main__':
    app.run(debug=True, port=5000)  # Ensure port is set to 5000 for Render