#!/usr/bin/env python3
"""
Check categories table structure
"""
import psycopg2
import os

# Aiven database connection
AIVEN_DB_URL = os.getenv('AIVEN_DATABASE_URL', "postgres://avnadmin:password@buymo-postgres-bester.h.aivencloud.com:15323/defaultdb?sslmode=require")

def check_categories():
    try:
        print("Connecting to Aiven database...")
        conn = psycopg2.connect(AIVEN_DB_URL)
        cur = conn.cursor()
        
        # Check categories table structure
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE table_name = 'categories' 
            ORDER BY ordinal_position
        """)
        columns = cur.fetchall()
        
        print("Categories table structure:")
        for col in columns:
            print(f"  {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")
        
        # Check existing categories
        cur.execute("SELECT * FROM categories")
        categories = cur.fetchall()
        print(f"\nExisting categories: {len(categories)}")
        for cat in categories:
            print(f"  {cat}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error checking categories: {e}")

if __name__ == "__main__":
    check_categories()
