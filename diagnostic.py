#!/usr/bin/env python3
"""
BuyMo Diagnostic Script
Run this to check the status of your application and identify issues
"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database

def print_header(text):
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60)

def check_env_variables():
    print_header("1. Environment Variables Check")
    
    required_vars = [
        'DATABASE_URL',
        'SECRET_KEY',
        'MAIL_SERVER',
        'MAIL_PORT',
        'MAIL_USERNAME',
        'MAIL_PASSWORD',
        'MAIL_DEFAULT_SENDER'
    ]
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Mask sensitive values
            if 'PASSWORD' in var or 'SECRET' in var:
                display_value = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
            else:
                display_value = value[:50] + "..." if len(value) > 50 else value
            print(f"✓ {var}: {display_value}")
        else:
            print(f"✗ {var}: NOT SET")
    
def check_database():
    print_header("2. Database Connection Check")
    
    try:
        conn = database.get_db_connection()
        print("✓ Database connection successful")
        
        cur = conn.cursor()
        
        # Check tables
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        print(f"\n✓ Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Check orders count
        cur.execute("SELECT COUNT(*) FROM orders")
        order_count = cur.fetchone()[0]
        print(f"\n✓ Total orders in database: {order_count}")
        
        if order_count > 0:
            cur.execute("SELECT id, user_id, tracking_number, total_amount, status FROM orders ORDER BY order_date DESC LIMIT 5")
            recent_orders = cur.fetchall()
            print("\n  Recent orders:")
            for order in recent_orders:
                print(f"    Order #{order[0]} - User {order[1]} - {order[2]} - R{order[3]} - {order[4]}")
        
        # Check users
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        print(f"\n✓ Total users: {user_count}")
        
        # Check admin users
        cur.execute("SELECT id, username, email, is_admin FROM users WHERE is_admin = TRUE")
        admins = cur.fetchall()
        print(f"\n✓ Admin users: {len(admins)}")
        for admin in admins:
            print(f"  - {admin[1]} ({admin[2]})")
        
        # Check cart items with timestamps
        cur.execute("""
            SELECT ci.id, ci.user_id, p.name, ci.quantity, ci.added_at,
                   EXTRACT(EPOCH FROM (NOW() - ci.added_at))/3600 as hours_ago
            FROM cart_items ci
            JOIN products p ON ci.product_id = p.id
            ORDER BY ci.added_at DESC
            LIMIT 10
        """)
        cart_items = cur.fetchall()
        print(f"\n✓ Cart items: {len(cart_items)}")
        if cart_items:
            print("  Recent cart items:")
            for item in cart_items:
                print(f"    User {item[1]}: {item[2]} x{item[3]} - Added {item[5]:.1f} hours ago")
        
        # Check abandoned carts
        cur.execute("""
            SELECT u.id, u.username, u.email, COUNT(ci.id) as item_count, MAX(ci.added_at) as last_added,
                   EXTRACT(EPOCH FROM (NOW() - MAX(ci.added_at)))/3600 as hours_ago
            FROM users u
            JOIN cart_items ci ON u.id = ci.user_id
            LEFT JOIN orders o ON u.id = o.user_id AND o.order_date > ci.added_at
            WHERE o.id IS NULL
            GROUP BY u.id, u.username, u.email
            HAVING MAX(ci.added_at) < NOW() - INTERVAL '1 hour'
            ORDER BY last_added DESC
        """)
        abandoned = cur.fetchall()
        print(f"\n✓ Abandoned carts (>1 hour old): {len(abandoned)}")
        for cart in abandoned:
            print(f"  - {cart[1]} ({cart[2]}): {cart[3]} items - {cart[5]:.1f} hours ago")
        
        cur.close()
        database.return_db_connection(conn)
        
    except Exception as e:
        print(f"✗ Database error: {str(e)}")
        import traceback
        traceback.print_exc()

def check_email_config():
    print_header("3. Email Configuration Check")
    
    mail_server = os.getenv('MAIL_SERVER')
    mail_port = os.getenv('MAIL_PORT')
    mail_username = os.getenv('MAIL_USERNAME')
    mail_password = os.getenv('MAIL_PASSWORD')
    
    if not mail_password:
        print("✗ MAIL_PASSWORD is not set - emails will NOT work!")
        return
    
    print(f"✓ Mail server: {mail_server}:{mail_port}")
    print(f"✓ Mail username: {mail_username}")
    print(f"✓ Mail password: {'*' * len(mail_password)} (set)")
    
    # Test SMTP connection
    try:
        import smtplib
        print(f"\n  Testing SMTP connection to {mail_server}:{mail_port}...")
        
        if mail_port == '465':
            server = smtplib.SMTP_SSL(mail_server, int(mail_port), timeout=10)
        else:
            server = smtplib.SMTP(mail_server, int(mail_port), timeout=10)
            server.starttls()
        
        server.login(mail_username, mail_password)
        print("  ✓ SMTP connection successful!")
        server.quit()
    except Exception as e:
        print(f"  ✗ SMTP connection failed: {str(e)}")

def main():
    print("\n" + "🔍 BuyMo Diagnostic Tool".center(60))
    print("This will help identify issues with your application\n")
    
    check_env_variables()
    check_database()
    check_email_config()
    
    print_header("Summary")
    print("Review the output above to identify any issues.")
    print("\nCommon fixes:")
    print("  - If MAIL_PASSWORD is not set, add it to your .env file")
    print("  - If no admin users exist, update a user: UPDATE users SET is_admin = TRUE WHERE email = 'your@email.com';")
    print("  - If no orders exist, the orders page will be empty (this is normal)")
    print("  - Abandoned carts only show items added >1 hour ago")
    print("\n")

if __name__ == "__main__":
    main()
