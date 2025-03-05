from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import database
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import os

# Create tables if they don't exist
database.create_tables()

# Create tables if they don't exist
database.create_tables()
app = Flask(__name__)
app.secret_key = 'Fliph106'  # Required for session management

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

    # Fetch the current product
    cur.execute('''
        SELECT p.id, p.name, p.price, p.description, p.image, c.id, c.name 
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.id = %s;
    ''', (product_id,))
    product = cur.fetchone()

    # Fetch related products (from the same category)
    if product:
        cur.execute('''
            SELECT p.id, p.name, p.price, p.description, p.image, c.name 
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE p.category_id = %s AND p.id != %s
            LIMIT 4;
        ''', (product[5], product_id))  # product[5] is the category ID
        related_products = cur.fetchall()
    else:
        related_products = []

    # Fetch reviews for the product
    cur.execute('''
        SELECT r.rating, r.comment, u.username, r.created_at 
        FROM reviews r
        JOIN users u ON r.user_id = u.id
        WHERE r.product_id = %s
        ORDER BY r.created_at DESC;
    ''', (product_id,))
    reviews = cur.fetchall()

    cur.close()
    conn.close()

    if product:
        return render_template('product.html', product=product, related_products=related_products, reviews=reviews)
    else:
        flash('Product not found.')
        return redirect(url_for('home'))
# Route to submit a review
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

    # Fetch categories from the database
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
        image = request.files.get('image')

        # Validate required fields
        if not name or not price or not category_id:
            flash('Name, Price, and Category are required.')
            return redirect(url_for('add_product'))

        # Handle image upload
        image_url = None
        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)
            image_url = f"uploads/{filename}"  # Relative path for the database
        else:
            flash('Invalid or missing image file.')
            return redirect(url_for('add_product'))

        # Insert product into the database
        try:
            conn = database.get_db_connection()
            cur = conn.cursor()
            cur.execute(
                'INSERT INTO products (name, price, description, image, category_id) VALUES (%s, %s, %s, %s, %s);',
                (name, float(price), description, image_url, int(category_id))
            )
            conn.commit()
            cur.close()
            conn.close()
            flash('Product added successfully!')
            return redirect(url_for('home'))
        except Exception as e:
            print(f"Error: {e}")  # Debug
            flash('An error occurred while adding the product.')
            return redirect(url_for('add_product'))

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
        return redirect(url_for('login'))  # Redirect to login after signup
    return render_template('signup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user_data = database.get_user_by_email(email)
        if user_data and check_password_hash(user_data[3], password):
            user = User(id=user_data[0], username=user_data[1], email=user_data[2],                 is_admin=user_data[4]  # Add this line
)
            login_user(user)
            flash('Login successful!')
            return redirect(url_for('home'))  # Redirect to home after login
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

    # Get search query and filters from the request
    search_query = request.args.get('query', '').strip()
    category_filter = request.args.get('category', '').strip()
    min_price = request.args.get('min_price', '').strip()
    max_price = request.args.get('max_price', '').strip()

    # Base query
    query = '''
        SELECT p.id, p.name, p.price, p.description, p.image, c.name 
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE 1=1
    '''
    params = []

    # Add search query filter
    if search_query:
        query += " AND p.name ILIKE %s"
        params.append(f"%{search_query}%")

    # Add category filter
    if category_filter:
        query += " AND c.name = %s"
        params.append(category_filter)

    # Add price range filter
    if min_price:
        query += " AND p.price >= %s"
        params.append(float(min_price))
    if max_price:
        query += " AND p.price <= %s"
        params.append(float(max_price))

    # Execute the query
    cur.execute(query, params)
    products = cur.fetchall()

    # Fetch all categories for the filter dropdown
    cur.execute('SELECT * FROM categories;')
    categories = cur.fetchall()

    cur.close()
    conn.close()

    return render_template('home.html', products=products, categories=categories, search_query=search_query, category_filter=category_filter, min_price=min_price, max_price=max_price)
def create_user(username, email, password, is_admin=False):
    conn = get_db_connection()
    cur = conn.cursor()
    password_hash = generate_password_hash(password)
    cur.execute(
        'INSERT INTO users (username, email, password_hash, is_admin) VALUES (%s, %s, %s, %s);',
        (username, email, password_hash, is_admin)
    )
    conn.commit()
    cur.close()
    conn.close()




if __name__ == '__main__':
    app.run(debug=True)