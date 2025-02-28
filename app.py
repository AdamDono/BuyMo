from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import database
from werkzeug.security import generate_password_hash, check_password_hash


app = Flask(__name__)
app.secret_key = 'Fliph106'  # Required for session management




@app.route('/')
@login_required
def index():
    return render_template('index.html', username=current_user.username)


# Product page - Display a single product
@app.route('/product/<int:product_id>')
def product(product_id):
    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM products WHERE id = %s;', (product_id,))
    product = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('product.html', product=product)

# Add a new product
@app.route('/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = request.form['price']
        description = request.form['description']
        image = request.form['image']

        conn = database.get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO products (name, price, description, image) VALUES (%s, %s, %s, %s);',
            (name, price, description, image)
        )
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('index'))
    return render_template('add_product.html')

@app.route('/get-started')
def get_started():
    return render_template('get_started.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Check if user already exists
        user = database.get_user_by_email(email)
        if user:
            flash('Email already registered. Please login.')
            return redirect(url_for('login'))

        # Create new user
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
            user = User(id=user_data[0], username=user_data[1], email=user_data[2])
            login_user(user)
            flash('Login successful!')
            return redirect(url_for('index'))
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
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s;', (user_id,))
    user_data = cur.fetchone()
    cur.close()
    conn.close()
    if user_data:
        return User(id=user_data[0], username=user_data[1], email=user_data[2])
    return None


if __name__ == '__main__':
    app.run(debug=True)