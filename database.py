import psycopg2
from werkzeug.security import generate_password_hash, check_password_hash


def get_db_connection():
    conn = psycopg2.connect(
        dbname="ecom_db",
        user="postgres",
        password="Fliph106",
        host="localhost",
        port="5433"
    )
    return conn


# Add these functions to your existing database.py
def get_user_details(user_id):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('''
        SELECT id, username, email, created_at, profile_image 
        FROM users WHERE id = %s
    ''', (user_id,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def update_user_profile(user_id, username, email, profile_image=None):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        if profile_image:
            cur.execute('''
                UPDATE users 
                SET username = %s, email = %s, profile_image = %s
                WHERE id = %s
            ''', (username, email, profile_image, user_id))
        else:
            cur.execute('''
                UPDATE users 
                SET username = %s, email = %s
                WHERE id = %s
            ''', (username, email, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating profile: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def update_user_password(user_id, new_password_hash):
    conn = get_db_connection()
    try:
        cur = conn.cursor()
        cur.execute('''
            UPDATE users 
            SET password_hash = %s
            WHERE id = %s
        ''', (new_password_hash, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating password: {e}")
        return False
    finally:
        cur.close()
        conn.close()

def create_user(username, email, password):
    conn = get_db_connection()
    cur = conn.cursor()
    password_hash = generate_password_hash(
        password,
        method='pbkdf2:sha256',  # Explicitly set method
        salt_length=16
    )
    cur.execute(
        'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s);',
        (username, email, password_hash)
    )
    conn.commit()
    cur.close()
    conn.close()

def get_user_by_email(email):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT * FROM users WHERE email = %s;', (email,))
    user = cur.fetchone()
    cur.close()
    conn.close()
    return user

def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()

    # Create cart_items table
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

    conn.commit()
    cur.close()
    conn.close()

# Call the function to create tables
create_tables()