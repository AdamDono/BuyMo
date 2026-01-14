#!/usr/bin/env python3
"""
Simulate PayFast notify webhook to test order completion
This will manually trigger the order completion for a pending order
"""
import requests
import sys

if len(sys.argv) < 2:
    print("Usage: python3 test_payfast_notify.py <pending_order_id>")
    print("\nAvailable pending orders:")
    print("  - Pending #35 - User 23 - R270.00")
    print("  - Pending #34 - User 23 - R180.00")
    print("  - Pending #33 - User 23 - R180.00")
    sys.exit(1)

pending_order_id = sys.argv[1]
user_id = sys.argv[2] if len(sys.argv) > 2 else "23"

# Simulate PayFast POST to notify endpoint
url = "https://buymo.onrender.com/payfast/notify"

# This is what PayFast sends
data = {
    'payment_status': 'COMPLETE',
    'm_payment_id': pending_order_id,
    'custom_int1': user_id,
    'amount_gross': '270.00',
    'pf_payment_id': '1234567'
}

print(f"\n🔄 Simulating PayFast notify for pending order #{pending_order_id}...")
print(f"   URL: {url}")
print(f"   Data: {data}\n")

try:
    response = requests.post(url, data=data, timeout=30)
    print(f"✅ Response: {response.status_code}")
    print(f"   Body: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ SUCCESS! Order should now be completed.")
        print("   Check:")
        print("   1. Run: python3 check_orders.py")
        print("   2. Check your email inbox")
        print("   3. Check /orders page on the website")
    else:
        print(f"\n❌ Failed with status {response.status_code}")
        
except Exception as e:
    print(f"❌ Error: {e}")
