#!/usr/bin/env python3
"""
Check pending_orders table structure
"""
import psycopg2
import os

# Aiven database connection
AIVEN_DB_URL = os.getenv('AIVEN_DATABASE_URL', "postgres://avnadmin:password@buymo-postgres-bester.h.aivencloud.com:15323/defaultdb?sslmode=require")

def check_pending_orders():
    try:
        print("Connecting to Aiven database...")
        conn = psycopg2.connect(AIVEN_DB_URL)
        cur = conn.cursor()
        
        # Check pending_orders table structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'pending_orders' 
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        print("Pending orders table structure:")
        for col in columns:
            print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error checking pending_orders: {e}")

if __name__ == "__main__":
    check_pending_orders()
