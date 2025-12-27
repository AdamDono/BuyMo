"""
Migration script to add delivery and status columns to orders table
Run this once to update your existing database
"""
import psycopg2
import os

def migrate_orders_table():
    # Get database connection
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
        print("Starting migration...")
        
        # Add new columns to orders table
        columns_to_add = [
            ("delivery_method", "VARCHAR(20) DEFAULT 'delivery'"),
            ("full_name", "VARCHAR(100)"),
            ("phone", "VARCHAR(20)"),
            ("street_address", "TEXT"),
            ("suburb", "VARCHAR(100)"),
            ("city", "VARCHAR(100)"),
            ("province", "VARCHAR(50)"),
            ("postal_code", "VARCHAR(10)"),
            ("delivery_fee", "DECIMAL(10, 2) DEFAULT 50.00"),
            ("status", "VARCHAR(50) DEFAULT 'processing'"),
            ("status_updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("pickup_date", "DATE")
        ]
        
        for column_name, column_type in columns_to_add:
            try:
                # Check if column exists
                cur.execute(f"""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name='orders' AND column_name='{column_name}'
                """)
                
                if cur.fetchone() is None:
                    # Column doesn't exist, add it
                    cur.execute(f"ALTER TABLE orders ADD COLUMN {column_name} {column_type}")
                    print(f"✓ Added column: {column_name}")
                else:
                    print(f"○ Column already exists: {column_name}")
                    
            except Exception as e:
                print(f"✗ Error adding column {column_name}: {str(e)}")
                conn.rollback()
                continue
        
        conn.commit()
        print("\n✅ Migration completed successfully!")
        print("\nYour orders table now has all the new columns for delivery tracking.")
        
    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {str(e)}")
        raise
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("ORDERS TABLE MIGRATION")
    print("=" * 60)
    print("\nThis will add delivery and status columns to your orders table.")
    print("Existing orders will not be affected.\n")
    
    response = input("Continue? (yes/no): ")
    if response.lower() == 'yes':
        migrate_orders_table()
    else:
        print("Migration cancelled.")
