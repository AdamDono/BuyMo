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


def create_user(username, email, password):
    conn = get_db_connection()
    cur = conn.cursor()
    password_hash = generate_password_hash(password)
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

    # Create reviews table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS reviews (
            id SERIAL PRIMARY KEY,
            product_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            rating INTEGER NOT NULL CHECK (rating >= 1 AND rating <= 5),
            comment TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products (id),
            FOREIGN KEY (user_id) REFERENCES users (id)
        );
    ''')

    conn.commit()
    cur.close()
    conn.close()