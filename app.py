from flask import Flask, render_template, request, redirect, url_for
import database

app = Flask(__name__)

# Homepage - Display all products
@app.route('/')
def index():
    conn = database.get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM products;')
    products = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', products=products)

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

@app.route('/signup')
def signup():
    return render_template('signup.html')

@app.route('/login')
def login():
    return render_template('login.html')





if __name__ == '__main__':
    app.run(debug=True)