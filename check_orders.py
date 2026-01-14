#!/usr/bin/env python3
"""
Quick script to check if orders exist and see their details
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database

def main():
    print("\n" + "="*60)
    print("  CHECKING ORDERS IN DATABASE")
    print("="*60 + "\n")
    
    conn = database.get_db_connection()
    cur = conn.cursor()
    
    # Get all orders
    cur.execute("""
        SELECT o.id, o.user_id, u.email, o.tracking_number, o.total_amount, 
               o.status, o.order_date, o.full_name, o.delivery_method
        FROM orders o
        JOIN users u ON o.user_id = u.id
        ORDER BY o.order_date DESC
        LIMIT 20
    """)
    orders = cur.fetchall()
    
    if not orders:
        print("❌ NO ORDERS FOUND IN DATABASE")
        print("\nThis means:")
        print("  1. No successful purchases have been completed")
        print("  2. PayFast notify webhook is not being called")
        print("  3. Or orders are being created but then deleted")
        
        # Check pending orders
        cur.execute("SELECT COUNT(*) FROM pending_orders")
        pending_count = cur.fetchone()[0]
        print(f"\n📋 Pending orders: {pending_count}")
        
        if pending_count > 0:
            cur.execute("SELECT id, user_id, total_amount, created_at FROM pending_orders ORDER BY created_at DESC LIMIT 5")
            pending = cur.fetchall()
            print("\nRecent pending orders (waiting for payment):")
            for p in pending:
                print(f"  - Pending #{p[0]} - User {p[1]} - R{p[2]} - {p[3]}")
            print("\n⚠️  These orders were created but PayFast notify was never called!")
            print("   This means PayFast is not sending the webhook to your server.")
    else:
        print(f"✅ FOUND {len(orders)} ORDERS\n")
        print("Recent orders:")
        print("-" * 100)
        for o in orders:
            print(f"Order #{o[0]:3d} | User: {o[2]:30s} | Tracking: {o[3]:15s} | R{o[4]:8.2f} | {o[5]:12s} | {o[6]}")
            print(f"           | Name: {o[7] or 'N/A':30s} | Method: {o[8] or 'N/A'}")
            print("-" * 100)
        
        # Check if emails were sent (we can't know for sure, but we can check logs)
        print("\n📧 To check if emails were sent:")
        print("   1. Check your Render logs for: '✓ Order confirmation email successfully queued'")
        print("   2. Check your email inbox (and spam folder)")
        print("   3. Check Brevo dashboard: https://app.brevo.com/")
    
    cur.close()
    database.return_db_connection(conn)
    print("\n")

if __name__ == "__main__":
    main()
