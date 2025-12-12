#!/usr/bin/env python3
"""
Add missing delivery_info_json column to pending_orders table
"""
import psycopg2
import os

# Aiven database connection
AIVEN_DB_URL = os.getenv('AIVEN_DATABASE_URL', "postgres://avnadmin:password@buymo-postgres-bester.h.aivencloud.com:15323/defaultdb?sslmode=require")

def fix_pending_orders():
    try:
        print("Connecting to Aiven database...")
        conn = psycopg2.connect(AIVEN_DB_URL)
        cur = conn.cursor()
        
        # Add delivery_info_json column if it doesn't exist
        try:
            cur.execute("""
                ALTER TABLE pending_orders 
                ADD COLUMN IF NOT EXISTS delivery_info_json TEXT
            """)
            conn.commit()
            print("Added delivery_info_json column to pending_orders table")
        except Exception as e:
            print(f"Column might already exist or error: {e}")
        
        # Check updated table structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'pending_orders' 
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        print("\nUpdated pending orders table structure:")
        for col in columns:
            print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error fixing pending_orders: {e}")

if __name__ == "__main__":
    fix_pending_orders()
