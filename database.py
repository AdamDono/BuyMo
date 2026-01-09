import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash
import os

def get_db_connection():
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:Fliph106@localhost:5433/ecom_db')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    from urllib.parse import urlparse
    url = urlparse(db_url)
    conn = psycopg2.connect(
        dbname=url.path[1:],
        user=url.username,
        password=url.password,
        host=url.hostname,
        port=url.port or 5432
    )
    return conn

def return_db_connection(conn):
    """Legacy compatibility - just close the connection"""
    if conn:
        conn.close()

def create_user(username, email, password):
    conn = get_db_connection()
    cur = conn.cursor()
    password_hash = generate_password_hash(
        password,
        method='pbkdf2:sha256',
        salt_length=16
    )
    cur.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s);',
        (username, email, password_hash)
    )
    conn.commit()
    cur.close()
    return_db_connection(conn)

def get_user_by_email(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE email = %s;', (email,))
    user = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return user

def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL,
            email VARCHAR(120) UNIQUE NOT NULL,
            password_hash VARCHAR(255) NOT NULL,
            is_admin BOOLEAN DEFAULT FALSE,
            profile_image VARCHAR(255),
            reset_token VARCHAR(100),
            reset_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Add reset columns if they don't exist
    cur.execute('''
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='reset_token') THEN
                ALTER TABLE users ADD COLUMN reset_token VARCHAR(100);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='reset_expiry') THEN
                ALTER TABLE users ADD COLUMN reset_expiry TIMESTAMP;
            END IF;
        END $$;
    ''')
    
    # Categories table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS categories (
            id SERIAL PRIMARY KEY,
            name VARCHAR(50) NOT NULL UNIQUE
        );
    ''')
    
    # Products table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS products (
            id SERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            price DECIMAL(10, 2) NOT NULL,
            description TEXT,
            image VARCHAR(255),
            category_id INTEGER REFERENCES categories(id),
            initial_quantity INTEGER NOT NULL,
            remaining_quantity INTEGER NOT NULL
        );
    ''')
    
    # Reviews table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            product_id INTEGER REFERENCES products(id),
            user_id INTEGER REFERENCES users(id),
            rating INTEGER CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Cart items table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS cart_items (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 1,
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
    ''')
    
    # Pending orders table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS pending_orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            total_amount DECIMAL(10, 2) NOT NULL,
            cart_items_json TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    ''')
    
    # Orders table for completed orders
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            tracking_number VARCHAR(20) UNIQUE,
            total_amount DECIMAL(10, 2) NOT NULL,
            order_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            delivery_method VARCHAR(20) DEFAULT 'delivery',
            full_name VARCHAR(100),
            phone VARCHAR(20),
            street_address TEXT,
            suburb VARCHAR(100),
            city VARCHAR(100),
            province VARCHAR(50),
            postal_code VARCHAR(10),
            delivery_fee DECIMAL(10, 2) DEFAULT 50.00,
            status VARCHAR(50) DEFAULT 'processing',
            status_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            pickup_date DATE,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    ''')
    
    # Add tracking_number column if it doesn't exist (for existing databases)
    cur.execute('''
        DO $$ 
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name='orders' AND column_name='tracking_number'
            ) THEN
                ALTER TABLE orders ADD COLUMN tracking_number VARCHAR(20) UNIQUE;
            END IF;
        END $$;
    ''')
    
    # Order items table for completed order details
    cur.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id SERIAL PRIMARY KEY,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            price_at_purchase DECIMAL(10, 2) NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders (id),
            FOREIGN KEY (product_id) REFERENCES products (id)
        );
    ''')
    
    # Wishlist table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS wishlist (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id)
        );
    ''')

    # Create indexes for better performance
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
        CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id);
    ''')

    conn.commit()
    cur.close()
    return_db_connection(conn)

def get_user_details(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, username, email, created_at, profile_image 
        FROM users 
        WHERE id = %s
    ''', (user_id,))
    user = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return user

def get_user_by_id(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
    user = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return user

def update_user_profile(user_id, username, email, profile_image=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if profile_image:
            cur.execute('UPDATE users SET username = %s, email = %s, profile_image = %s WHERE id = %s',
                      (username, email, profile_image, user_id))
        else:
            cur.execute('UPDATE users SET username = %s, email = %s WHERE id = %s',
                      (username, email, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating profile: {e}")
        return False
    finally:
        cur.close()
        return_db_connection(conn)

def update_user_password(user_id, new_password_hash):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('UPDATE users SET password_hash = %s WHERE id = %s',
                   (new_password_hash, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
    finally:
        cur.close()
        return_db_connection(conn)


def set_user_reset_token(email, token, expiry):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        UPDATE users 
        SET reset_token = %s, reset_expiry = %s 
        WHERE email = %s
    ''', (token, expiry, email))
    conn.commit()
    cur.close()
    return_db_connection(conn)

def get_user_by_reset_token(token):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, username, email, reset_expiry 
        FROM users 
        WHERE reset_token = %s
    ''', (token,))
    user = cur.fetchone()
    cur.close()
    return_db_connection(conn)
    return user

def clear_user_reset_token(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        UPDATE users 
        SET reset_token = NULL, reset_expiry = NULL 
        WHERE id = %s
    ''', (user_id,))
    conn.commit()
    cur.close()
    return_db_connection(conn)

def toggle_wishlist_item(user_id, product_id):
    """Toggle a product in the user's wishlist. Returns True if added, False if removed."""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Check if exists
    cur.execute('SELECT id FROM wishlist WHERE user_id = %s AND product_id = %s', (user_id, product_id))
    exists = cur.fetchone()
    
    if exists:
        cur.execute('DELETE FROM wishlist WHERE id = %s', (exists[0],))
        added = False
    else:
        cur.execute('INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)', (user_id, product_id))
        added = True
        
    conn.commit()
    cur.close()
    return_db_connection(conn)
    return added

def get_user_wishlist(user_id):
    """Get all products in a user's wishlist"""
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.* 
        FROM products p
        JOIN wishlist w ON p.id = w.product_id
        WHERE w.user_id = %s
        ORDER BY w.created_at DESC
    ''', (user_id,))
    products = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    return products

# Call the function to create tables
create_tables()