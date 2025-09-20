import psycopg2
from urllib.parse import urlparse
from werkzeug.security import generate_password_hash

# Your Render DB URL
db_url = "postgresql://buymo_db_user:97rPJTI0zpfZIOXTrHoQyVjPqQ6ktbn7@dpg-d36k5v2dbo4c73dsnla0-a.oregon-postgres.render.com/buymo_db"

# Parse the URL
url = urlparse(db_url)
conn = psycopg2.connect(
    dbname=url.path[1:],
    user=url.username,
    password=url.password,
    host=url.hostname,
    port=url.port or 5432
)

cur = conn.cursor()

# Drop tables if they exist (careful: this deletes all data)
cur.execute("DROP TABLE IF EXISTS order_items CASCADE;")
cur.execute("DROP TABLE IF EXISTS orders CASCADE;")
cur.execute("DROP TABLE IF EXISTS pending_orders CASCADE;")
cur.execute("DROP TABLE IF EXISTS cart_items CASCADE;")
cur.execute("DROP TABLE IF EXISTS reviews CASCADE;")
cur.execute("DROP TABLE IF EXISTS products CASCADE;")
cur.execute("DROP TABLE IF EXISTS categories CASCADE;")
cur.execute("DROP TABLE IF EXISTS users CASCADE;")

# Create tables
cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        username VARCHAR(50) NOT NULL,
        email VARCHAR(120) UNIQUE NOT NULL,
        password_hash VARCHAR(255) NOT NULL,
        is_admin BOOLEAN DEFAULT FALSE,
        profile_image VARCHAR(255),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS categories (
        id SERIAL PRIMARY KEY,
        name VARCHAR(50) NOT NULL UNIQUE
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id SERIAL PRIMARY KEY,
        name VARCHAR(100) NOT NULL,
        price DECIMAL(10, 2) NOT NULL,
        description TEXT,
        image VARCHAR(255),
        category_id INTEGER REFERENCES categories(id),
        initial_quantity INTEGER NOT NULL,
        remaining_quantity INTEGER NOT NULL,
        CONSTRAINT unique_product_name UNIQUE (name)
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS reviews (
        id SERIAL PRIMARY KEY,
        product_id INTEGER REFERENCES products(id),
        user_id INTEGER REFERENCES users(id),
        rating INTEGER CHECK (rating >= 1 AND rating <= 5),
        comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS cart_items (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS pending_orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        total_amount DECIMAL(10, 2) NOT NULL,
        cart_items_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id SERIAL PRIMARY KEY,
        user_id INTEGER NOT NULL,
        total_amount DECIMAL(10, 2) NOT NULL,
        order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (id)
    );
""")

cur.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        id SERIAL PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        price_at_purchase DECIMAL(10, 2) NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders (id),
        FOREIGN KEY (product_id) REFERENCES products (id)
    );
""")

conn.commit()
print("Tables created successfully.")

# Insert admin user if not exists
admin_hash = generate_password_hash('admin123', method='pbkdf2:sha256', salt_length=16)
cur.execute("""
    INSERT INTO users (username, email, password_hash, is_admin) 
    VALUES ('Admin', 'admin@buymo.com', %s, TRUE) 
    ON CONFLICT (email) DO NOTHING;
""", (admin_hash,))
conn.commit()
print("Admin user created: admin@buymo.com (password: admin123)")

# Insert sample categories if none exist
cur.execute("""
    INSERT INTO categories (name) VALUES ('Electronics'), ('Clothing'), ('Books') 
    ON CONFLICT (name) DO NOTHING;
""")
conn.commit()
print("Sample categories added.")

# Insert sample products if none exist
cur.execute("""
    INSERT INTO products (name, price, description, image, category_id, initial_quantity, remaining_quantity) 
    VALUES 
    ('Wireless Headphones', 299.99, 'High-quality wireless headphones', 'uploads/headphones.jpg', 1, 50, 50),
    ('T-Shirt', 49.99, 'Comfortable cotton t-shirt', 'uploads/tshirt.jpg', 2, 100, 100),
    ('The Great Gatsby', 19.99, 'Classic novel by F. Scott Fitzgerald', 'uploads/gatsby.jpg', 3, 25, 25)
    ON CONFLICT (name) DO NOTHING;
""")
conn.commit()
print("Sample products added.")

cur.close()
conn.close()
print("Setup complete! Log in as admin@buymo.com with password 'admin123' to add more products.")