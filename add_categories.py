#!/usr/bin/env python3
"""
Add default categories to Aiven database
"""
import psycopg2
import os

# Aiven database connection
AIVEN_DB_URL = os.getenv('AIVEN_DATABASE_URL', "postgres://avnadmin:password@buymo-postgres-bester.h.aivencloud.com:15323/defaultdb?sslmode=require")

def add_categories():
    try:
        print("Connecting to Aiven database...")
        conn = psycopg2.connect(AIVEN_DB_URL)
        cur = conn.cursor()
        
        # Check existing categories
        cur.execute("SELECT COUNT(*) FROM categories")
        count = cur.fetchone()[0]
        print(f"Current categories: {count}")
        
        if count == 0:
            # Add default categories
            categories = [
                'Electronics',
                'Clothing', 
                'Books',
                'Home & Garden',
                'Sports',
                'Toys',
                'Food',
                'Beauty'
            ]
            
            for name in categories:
                cur.execute(
                    "INSERT INTO categories (name) VALUES (%s)",
                    (name,)
                )
                print(f"Added category: {name}")
            
            conn.commit()
            print("Categories added successfully!")
        else:
            print("Categories already exist")
        
        # Show all categories
        cur.execute("SELECT id, name FROM categories")
        categories = cur.fetchall()
        print("\nAll categories:")
        for cat in categories:
            print(f"  {cat[0]}: {cat[1]}")
        
        cur.close()
        conn.close()
        
    except Exception as e:
        print(f"Error adding categories: {e}")

if __name__ == "__main__":
    add_categories()
