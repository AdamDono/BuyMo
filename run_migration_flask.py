"""
Run migration using Flask's exact database connection
This ensures we're updating the same database Flask uses
"""
from app import app
import database

def migrate():
    with app.app_context():
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        try:
            print("=" * 60)
            print("MIGRATING ORDERS TABLE (Using Flask's DB Connection)")
            print("=" * 60)
            
            # Check what database we're connected to
            cur.execute("SELECT current_database()")
            db_name = cur.fetchone()[0]
            print(f"\nConnected to database: {db_name}")
            
            # Check existing columns
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='orders'
            """)
            existing = [row[0] for row in cur.fetchall()]
            print(f"Existing columns: {len(existing)}")
            
            # Add columns
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
            
            added_count = 0
            for col_name, col_type in columns_to_add:
                if col_name not in existing:
                    try:
                        cur.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {col_type}")
                        conn.commit()
                        print(f"✓ Added: {col_name}")
                        added_count += 1
                    except Exception as e:
                        print(f"✗ Error adding {col_name}: {str(e)}")
                        conn.rollback()
                else:
                    print(f"○ Exists: {col_name}")
            
            # Verify
            cur.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='orders'
                ORDER BY ordinal_position
            """)
            final = [row[0] for row in cur.fetchall()]
            
            print(f"\n{'=' * 60}")
            print(f"✅ Migration complete! Added {added_count} columns")
            print(f"Total columns in orders table: {len(final)}")
            print(f"{'=' * 60}")
            
            # Test the query that was failing
            print("\nTesting orders query...")
            cur.execute("""
                SELECT o.id, o.total_amount, o.order_date, o.status, o.delivery_method
                FROM orders o
                LIMIT 1
            """)
            print("✓ Orders query works!")
            
            print("\nTesting checkout query...")
            cur.execute("""
                SELECT full_name, phone, street_address, suburb, city, province, postal_code
                FROM orders
                LIMIT 1
            """)
            print("✓ Checkout query works!")
            
            print("\n🎉 All done! Restart Flask and it should work!")
            
        except Exception as e:
            conn.rollback()
            print(f"\n❌ Migration failed: {str(e)}")
            raise
        finally:
            cur.close()
            conn.close()

if __name__ == "__main__":
    migrate()
