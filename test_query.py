"""
Test the exact query that's failing
"""
import database

conn = database.get_db_connection()
cur = conn.cursor()

try:
    print("Testing the orders query...")
    cur.execute('''
        SELECT o.id, o.total_amount, o.order_date, o.status, o.delivery_method,
               o.full_name, o.phone, o.street_address, o.suburb, o.city, 
               o.province, o.postal_code, o.delivery_fee, o.pickup_date
        FROM orders o
        WHERE o.user_id = 1
        ORDER BY o.order_date DESC
    ''')
    
    orders = cur.fetchall()
    print(f"✓ Query successful! Found {len(orders)} orders")
    
    if orders:
        print("\nFirst order:")
        print(orders[0])
    
except Exception as e:
    print(f"✗ Query failed: {str(e)}")
finally:
    cur.close()
    conn.close()
