#!/usr/bin/env python3
"""
Get the latest pending order details for testing
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import database

conn = database.get_db_connection()
cur = conn.cursor()

# Get the most recent pending order
cur.execute("""
    SELECT po.id, po.user_id, u.email, po.total_amount, po.created_at
    FROM pending_orders po
    JOIN users u ON po.user_id = u.id
    ORDER BY po.created_at DESC
    LIMIT 1
""")

pending = cur.fetchone()

if pending:
    print(f"\n✅ Most Recent Pending Order:")
    print(f"   Pending Order ID: {pending[0]}")
    print(f"   User ID: {pending[1]}")
    print(f"   User Email: {pending[2]}")
    print(f"   Total Amount: R{pending[3]}")
    print(f"   Created: {pending[4]}")
    print(f"\n📋 To test this order, run:")
    print(f"\n   curl -X POST https://buymo.onrender.com/payfast/notify \\")
    print(f"     -d 'payment_status=COMPLETE' \\")
    print(f"     -d 'm_payment_id={pending[0]}' \\")
    print(f"     -d 'custom_int1={pending[1]}'")
    print(f"\n   Then check email: {pending[2]}\n")
else:
    print("\n❌ No pending orders found")

cur.close()
database.return_db_connection(conn)
