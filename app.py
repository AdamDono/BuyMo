from flask import Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import database
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

# Create tables if they don't exist
database.create_tables()

app = Flask(__name__)
app.secret_key = 'Fliph106'  # Required for session management

@app.template_filter('zar')
def format_zar(amount):
    return f"R{amount:,.2f}".replace(",", " ")

# Configure upload folder and allowed extensions
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

@app.route('/')
def index():
    return redirect(url_for('signup'))

@app.route('/product/<int:product_id>')
def product(product_id):
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    # Get the product with category
    cur.execute('''
       SELECT p.id, p.name, p.price, p.description, p.image, 
               p.remaining_quantity, p.initial_quantity,  -- ADD THESE
               c.id, c.name 
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.id = %s;
    ''', (product_id,))
    product = cur.fetchone()
    
    # Get reviews for the product
    cur.execute('''
        SELECT r.rating, r.comment, u.username, r.created_at 
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = %s
        ORDER BY r.created_at DESC;
    ''', (product_id,))
    reviews = cur.fetchall()
    
    # Calculate average rating
    avg_rating = 0
    if reviews:
        avg_rating = sum(review[0] for review in reviews) / len(reviews)
    
    # Get related products
    related_products = []
    if product:
        cur.execute('''
            SELECT p.id, p.name, p.price, p.description, p.image 
            FROM products p
            WHERE p.category_id = %s AND p.id != %s
            LIMIT 4;
        ''', (product[5], product_id))
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
        print(f"Error: {e}")
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

    # Fetch categories
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

        if not all([name, price, category_id]):
            flash('Name, Price, and Category are required.')
            return redirect(url_for('add_product'))

        image_url = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            image_url = f"uploads/{filename}"

        try:
            conn = database.get_db_connection()
            cur = conn.cursor()
            cur.execute('''
                INSERT INTO products 
                (name, price, description, image, category_id, initial_quantity, remaining_quantity)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (name, float(price), description, image_url, int(category_id), quantity, quantity))
            conn.commit()
            flash('Product added successfully!')
            return redirect(url_for('home'))
        except Exception as e:
            print(f"Error: {e}")
            flash('An error occurred while adding the product.')
        finally:
            cur.close()
            conn.close()

    return render_template('add_product.html', categories=categories)

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
        if user_data and check_password_hash(user_data[3], password):
            user = User(id=user_data[0], username=user_data[1], email=user_data[2], is_admin=user_data[4])
            login_user(user)
            flash('Login successful!')
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.')
    return redirect(url_for('index'))

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

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

@app.route('/home')
@login_required
def home():
    conn = database.get_db_connection()
    cur = conn.cursor()

    search_query = request.args.get('query', '').strip()
    category_filter = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()

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

    cur.close()
    conn.close()

    return render_template('home.html', products=products, categories=categories, search_query=search_query, category_filter=category_filter, min_price=min_price, max_price=max_price)

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
        print(f"Error: {e}")
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
    
    # Make sure this query matches your database structure
    cur.execute('''
        SELECT ci.id, p.name, p.price, p.image, ci.quantity 
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        WHERE ci.user_id = %s
    ''', (current_user.id,))
    cart_items = cur.fetchall()

    # Calculate total
    total_price = sum(item[2] * item[4] for item in cart_items)  # price * quantity
    
    cur.close()
    conn.close()
    
    return render_template('cart.html', 
                         cart_items=cart_items, 
                         total_price=total_price)
@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        
        cur.execute('''
            SELECT p.id, c.quantity, p.remaining_quantity
            FROM cart_items c
            JOIN products p ON c.product_id = p.id
            WHERE c.user_id = %s
        ''', (current_user.id,))
        cart_items = cur.fetchall()

        for item in cart_items:
            if item[2] < item[1]:
                flash(f'Not enough stock for product ID {item[0]}')
                return redirect(url_for('cart'))

        for item in cart_items:
            cur.execute('''
                UPDATE products 
                SET remaining_quantity = remaining_quantity - %s
                WHERE id = %s
            ''', (item[1], item[0]))
            
            cur.execute('''
                DELETE FROM cart_items 
                WHERE user_id = %s AND product_id = %s
            ''', (current_user.id, item[0]))
        
        conn.commit()
        flash('Order completed successfully!')
    except Exception as e:
        conn.rollback()
        flash(f'Error during checkout: {str(e)}', 'error')
    finally:
        conn.close()
    
    return redirect(url_for('home'))


# Cart Item Removal
@app.route('/remove-from-cart/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    conn = database.get_db_connection()
    try:
        cur = conn.cursor()
        
        # Verify ownership before deletion
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

# Cart Quantity Update
@app.route('/update-cart/<int:item_id>', methods=['POST'])
@login_required
def update_cart(item_id):
    try:
        quantity = int(request.form['quantity'])
        if quantity < 1:
            return redirect(url_for('remove_from_cart', item_id=item_id))
            
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        # Verify item belongs to user before updating
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
            # Get existing image path FIRST
            image_url = product[4]  # Assuming image path is at index 4
            
            # Handle new image upload if provided
            if 'image' in request.files:
                image = request.files['image']
                if image.filename != '' and allowed_file(image.filename):
                    filename = secure_filename(image.filename)
                    image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    image.save(image_path)
                    image_url = f"uploads/{filename}"  # Update only if new image is valid
            
            # Update product
            cur.execute('''
                UPDATE products 
                SET name = %s, price = %s, description = %s,
                    image = %s, category_id = %s
                WHERE id = %s
            ''', (
                request.form['name'],
                float(request.form['price']),
                request.form['description'],
                image_url,  # Now always defined
                int(request.form['category']),
                product_id
            ))
            
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
        profile_image = None
        
        # Handle file upload
        if 'profile_image' in request.files:
            file = request.files['profile_image']
            if file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(f"user_{current_user.id}_{file.filename}")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles', filename)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                file.save(filepath)
                profile_image = f"uploads/profiles/{filename}"
                
                # Delete old image if exists
                if user[4]:  # profile_image field
                    old_path = os.path.join(app.static_folder, user[4])
                    if os.path.exists(old_path):
                        os.remove(old_path)
        
        if update_user_profile(current_user.id, username, email, profile_image):
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('profile'))
        else:
            flash('Error updating profile', 'danger')
    
    return render_template('profile.html', user=user)

@app.route('/profile/change-password', methods=['POST'])
@login_required
def change_password():
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Verify current password
    user = get_user_by_id(current_user.id)
    if not check_password_hash(user['password_hash'], current_password):
        flash('Current password is incorrect', 'danger')
        return redirect(url_for('profile'))
    
    # Validate new password
    if new_password != confirm_password:
        flash('New passwords do not match', 'danger')
        return redirect(url_for('profile'))
    
    if len(new_password) < 8:
        flash('Password must be at least 8 characters', 'danger')
        return redirect(url_for('profile'))
    
    # Update password
    new_hash = generate_password_hash(new_password)
    if update_user_password(current_user.id, new_hash):
        flash('Password updated successfully!', 'success')
        # Logout after password change for security
        logout_user()
        return redirect(url_for('login'))
    else:
        flash('Error updating password', 'danger')
        return redirect(url_for('profile'))

if __name__ == '__main__':
    app.run(debug=True)