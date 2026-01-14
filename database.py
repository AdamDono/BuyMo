import psycopg2
from psycopg2 import pool
from werkzeug.security import generate_password_hash, check_password_hash
import os
from urllib.parse import urlparse

# Global connection pool
_db_pool = None

def _configure_db_url():
    db_url = os.getenv('DATABASE_URL', 'postgresql://postgres:Fliph106@localhost:5433/ecom_db')
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    
    # Crucial for Render/Aiven/Neon cloud databases: enforce SSL
    if 'localhost' not in db_url and '127.0.0.1' not in db_url:
        if 'sslmode' not in db_url:
            separator = '&' if '?' in db_url else '?'
            db_url += f"{separator}sslmode=require"
    return db_url

def init_pool():
    global _db_pool
    if _db_pool is None:
        db_url = _configure_db_url()
        try:
            _db_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=20, 
                dsn=db_url
            )
            print("Database connection pool initialized successfully.")
        except Exception as e:
            print(f"Error initializing connection pool: {e}")

def get_db_connection():
    global _db_pool
    if _db_pool is None:
        init_pool()
        
    if _db_pool:
        try:
            return _db_pool.getconn()
        except Exception as e:
            print(f"Error getting connection from pool: {e}")
    
    # Absolute fallback to direct connection
    db_url = _configure_db_url()
    return psycopg2.connect(db_url)

def return_db_connection(conn):
    global _db_pool
    if _db_pool and conn:
        try:
            _db_pool.putconn(conn)
        except Exception as e:
            print(f"Error returning connection to pool: {e}")
            conn.close()
    elif conn:
        conn.close()

def close_pool():
    global _db_pool
    if _db_pool:
        try:
            _db_pool.closeall()
        except Exception as e:
            print(f"Error closing pool: {e}")
        finally:
            _db_pool = None
            print("Database pool closed and reset.")

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
            delivery_info_json TEXT,
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
            driver_name VARCHAR(100),
            driver_phone VARCHAR(20),
            tracking_link TEXT,
            shipped_date VARCHAR(50),
            estimated_delivery_date VARCHAR(50),
            delivered_at VARCHAR(50),
            proof_of_delivery TEXT,
            delivery_notes TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    ''')
    
    # Add extra columns if they don't exist
    cur.execute('''
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='pending_orders' AND column_name='delivery_info_json') THEN
                ALTER TABLE pending_orders ADD COLUMN delivery_info_json TEXT;
            END IF;
        END $$;
    ''')

    # Add extra columns if they don't exist
    cur.execute('''
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='driver_name') THEN
                ALTER TABLE orders ADD COLUMN driver_name VARCHAR(100);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='driver_phone') THEN
                ALTER TABLE orders ADD COLUMN driver_phone VARCHAR(20);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='tracking_link') THEN
                ALTER TABLE orders ADD COLUMN tracking_link TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='shipped_date') THEN
                ALTER TABLE orders ADD COLUMN shipped_date VARCHAR(50);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='estimated_delivery_date') THEN
                ALTER TABLE orders ADD COLUMN estimated_delivery_date VARCHAR(50);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='delivered_at') THEN
                ALTER TABLE orders ADD COLUMN delivered_at VARCHAR(50);
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='proof_of_delivery') THEN
                ALTER TABLE orders ADD COLUMN proof_of_delivery TEXT;
            END IF;
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='orders' AND column_name='delivery_notes') THEN
                ALTER TABLE orders ADD COLUMN delivery_notes TEXT;
            END IF;
        END $$;
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
    
    # Coupons table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS coupons (
            id SERIAL PRIMARY KEY,
            code VARCHAR(50) UNIQUE NOT NULL,
            discount_type VARCHAR(20) NOT NULL, -- 'percentage' or 'fixed'
            discount_value DECIMAL(10, 2) NOT NULL,
            min_purchase DECIMAL(10, 2) DEFAULT 0,
            valid_until TIMESTAMP,
            usage_limit INTEGER,
            usage_count INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    ''')
    
    # Wishlist table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS wishlist (
            id SERIAL PRIMARY KEY,
            user_id INTEGER REFERENCES users(id),
            product_id INTEGER REFERENCES products(id),
            added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, product_id)
        );
    ''')
    
    # Migration: Ensure wishlist has added_at column
    cur.execute('''
        DO $$ 
        BEGIN 
            IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='wishlist' AND column_name='added_at') THEN
                ALTER TABLE wishlist ADD COLUMN added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;
            END IF;
        END $$;
    ''')
    
    # Create indexes for better performance
    cur.execute('''
        CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
        CREATE INDEX IF NOT EXISTS idx_cart_user ON cart_items(user_id);
        CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
        CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);
        CREATE INDEX IF NOT EXISTS idx_wishlist_user ON wishlist(user_id);
        CREATE INDEX IF NOT EXISTS idx_coupons_code ON coupons(code);
    ''')

    conn.commit()
    cur.close()
    return_db_connection(conn)

def toggle_wishlist_item(user_id, product_id):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('SELECT id FROM wishlist WHERE user_id = %s AND product_id = %s', (user_id, product_id))
        exists = cur.fetchone()
        
        if exists:
            cur.execute('DELETE FROM wishlist WHERE user_id = %s AND product_id = %s', (user_id, product_id))
            added = False
            message = "Removed from wishlist"
        else:
            cur.execute('INSERT INTO wishlist (user_id, product_id) VALUES (%s, %s)', (user_id, product_id))
            added = True
            message = "Added to wishlist"
        
        conn.commit()
        return True, added, message
    except Exception as e:
        print(f"Wishlist error: {e}")
        return False, False, str(e)
    finally:
        cur.close()
        return_db_connection(conn)

def get_user_wishlist(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT p.id, p.name, p.price, p.image 
        FROM wishlist w
        JOIN products p ON w.product_id = p.id
        WHERE w.user_id = %s
        ORDER BY w.added_at DESC
    ''', (user_id,))
    items = cur.fetchall()
    cur.close()
    return_db_connection(conn)
    return items

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
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM users WHERE id = %s', (user_id,))
        user = cur.fetchone()
        cur.close()
        return_db_connection(conn)
        return user
    except psycopg2.OperationalError:
        # Connection might be dead, try once more with fresh connection
        if conn:
            try:
                conn.close()
            except:
                pass
        global _db_pool
        if _db_pool:
            try:
                _db_pool.closeall()
            except:
                pass
            _db_pool = None # Force re-init
        
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

# Call the function to create tables
create_tables()