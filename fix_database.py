"""
Direct fix - Add columns with explicit schema
"""
import psycopg2
import os

def fix_database():
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
    conn.autocommit = False
    
    cur = conn.cursor()
    
    try:
        # First, let's see what tables exist
        cur.execute("""
            SELECT schemaname, tablename 
            FROM pg_tables 
            WHERE tablename = 'orders'
        """)
        tables = cur.fetchall()
        print(f"Found orders tables: {tables}")
        
        # Check current columns
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='orders' AND table_schema='public'
        """)
        existing = [row[0] for row in cur.fetchall()]
        print(f"\nExisting columns: {existing}")
        
        # Try to add columns with explicit public schema
        columns_to_add = [
            "delivery_method VARCHAR(20) DEFAULT 'delivery'",
            "full_name VARCHAR(100)",
            "phone VARCHAR(20)",
            "street_address TEXT",
            "suburb VARCHAR(100)",
            "city VARCHAR(100)",
            "province VARCHAR(50)",
            "postal_code VARCHAR(10)",
            "delivery_fee DECIMAL(10, 2) DEFAULT 50.00",
            "status VARCHAR(50) DEFAULT 'processing'",
            "status_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
            "pickup_date DATE"
        ]
        
        for col_def in columns_to_add:
            col_name = col_def.split()[0]
            if col_name not in existing:
                try:
                    sql = f"ALTER TABLE public.orders ADD COLUMN {col_def}"
                    print(f"\nExecuting: {sql}")
                    cur.execute(sql)
                    conn.commit()
                    print(f"✓ Added: {col_name}")
                except Exception as e:
                    print(f"✗ Error with {col_name}: {str(e)}")
                    conn.rollback()
            else:
                print(f"○ Already exists: {col_name}")
        
        # Verify
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='orders' AND table_schema='public'
            ORDER BY ordinal_position
        """)
        final_cols = [row[0] for row in cur.fetchall()]
        print(f"\n\nFinal columns in orders table:")
        for col in final_cols:
            print(f"  - {col}")
        
        print("\n✅ Done!")
        
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    fix_database()
