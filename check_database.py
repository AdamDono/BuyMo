"""
Check if the orders table has the new columns
"""
import psycopg2
import os

def check_orders_table():
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
    
    cur = conn.cursor()
    
    try:
        # Get all columns from orders table
        cur.execute("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name='orders'
            ORDER BY ordinal_position
        """)
        
        columns = cur.fetchall()
        
        print("=" * 60)
        print("ORDERS TABLE COLUMNS")
        print("=" * 60)
        
        for col_name, col_type in columns:
            print(f"  {col_name:<25} {col_type}")
        
        print("\n" + "=" * 60)
        
        # Check for specific new columns
        new_columns = ['status', 'delivery_method', 'full_name', 'phone', 
                      'street_address', 'suburb', 'city', 'province', 
                      'postal_code', 'delivery_fee', 'pickup_date']
        
        existing_cols = [col[0] for col in columns]
        
        print("\nNEW COLUMNS STATUS:")
        print("=" * 60)
        for col in new_columns:
            status = "✓ EXISTS" if col in existing_cols else "✗ MISSING"
            print(f"  {col:<25} {status}")
        
    except Exception as e:
        print(f"Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    check_orders_table()
