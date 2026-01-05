#!/usr/bin/env python3
"""
Email Testing Script for BuyMo
This script tests the email configuration and sends test emails
"""

import os
import sys
from dotenv import load_dotenv
from flask import Flask
from flask_mail import Mail, Message
import logging

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Create a minimal Flask app for testing
app = Flask(__name__)

# Mail Configuration
app.config['MAIL_SERVER'] = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
app.config['MAIL_PORT'] = int(os.getenv('MAIL_PORT', 587))
app.config['MAIL_USE_TLS'] = os.getenv('MAIL_USE_TLS', 'True').lower() == 'true'
app.config['MAIL_USE_SSL'] = os.getenv('MAIL_USE_SSL', 'False').lower() == 'true'
app.config['MAIL_USERNAME'] = os.getenv('MAIL_USERNAME')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# Parse MAIL_DEFAULT_SENDER to extract just the email if it's in "Name <email>" format
default_sender = os.getenv('MAIL_DEFAULT_SENDER', app.config['MAIL_USERNAME'])
if '<' in default_sender and '>' in default_sender:
    import re
    email_match = re.search(r'<(.+?)>', default_sender)
    if email_match:
        app.config['MAIL_DEFAULT_SENDER'] = email_match.group(1)
    else:
        app.config['MAIL_DEFAULT_SENDER'] = default_sender
else:
    app.config['MAIL_DEFAULT_SENDER'] = default_sender

app.config['MAIL_DEBUG'] = True

# Initialize Mail
mail = Mail(app)

def print_config():
    """Print the current mail configuration"""
    print("\n" + "="*60)
    print("EMAIL CONFIGURATION")
    print("="*60)
    print(f"Server:   {app.config['MAIL_SERVER']}")
    print(f"Port:     {app.config['MAIL_PORT']}")
    print(f"TLS:      {app.config['MAIL_USE_TLS']}")
    print(f"SSL:      {app.config['MAIL_USE_SSL']}")
    print(f"Username: {app.config['MAIL_USERNAME']}")
    print(f"Sender:   {app.config['MAIL_DEFAULT_SENDER']}")
    print(f"Password: {'SET ✓' if app.config['MAIL_PASSWORD'] else 'NOT SET ✗'}")
    print("="*60 + "\n")

def test_simple_email(recipient):
    """Send a simple test email"""
    with app.app_context():
        try:
            print(f"\n📧 Sending test email to {recipient}...")
            
            msg = Message(
                "BuyMo Email Test",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipient]
            )
            msg.body = "This is a test email from BuyMo. If you receive this, the email configuration is working correctly!"
            msg.html = "<h1>Test Email</h1><p>This is a test email from BuyMo. If you receive this, the email configuration is working correctly!</p>"
            
            mail.send(msg)
            print(f"✓ Email sent successfully to {recipient}")
            return True
        except Exception as e:
            print(f"✗ Failed to send email: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return False

def test_welcome_email(recipient, username="TestUser"):
    """Send a test welcome email using the actual template"""
    with app.app_context():
        try:
            print(f"\n📧 Sending welcome email to {recipient}...")
            
            # Read the welcome template
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'emails', 'welcome.html')
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Replace the username placeholder
            html_content = template_content.replace('{{ username }}', username)
            
            msg = Message(
                f"Welcome to BuyMo, {username}! 🛍️",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipient]
            )
            msg.html = html_content
            
            mail.send(msg)
            print(f"✓ Welcome email sent successfully to {recipient}")
            return True
        except Exception as e:
            print(f"✗ Failed to send welcome email: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return False

def test_order_email(recipient):
    """Send a test order confirmation email using the actual template"""
    with app.app_context():
        try:
            print(f"\n📧 Sending order confirmation email to {recipient}...")
            
            # Read the order confirmation template
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'emails', 'order_confirmation.html')
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Replace placeholders with test data
            html_content = template_content.replace('{{ order.full_name }}', 'Test User')
            html_content = html_content.replace('{{ order.tracking_number }}', 'BM-20260105-TEST1')
            html_content = html_content.replace('{{ "{:,.2f}".format(order.total_amount) }}', '1,234.56')
            html_content = html_content.replace('{{ order.delivery_method }}', 'delivery')
            html_content = html_content.replace('{{ order.items_count }}', '3')
            
            msg = Message(
                "Order Confirmation - BM-20260105-TEST1",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipient]
            )
            msg.html = html_content
            
            mail.send(msg)
            print(f"✓ Order confirmation email sent successfully to {recipient}")
            return True
        except Exception as e:
            print(f"✗ Failed to send order confirmation email: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return False

def test_reset_password_email(recipient, username="TestUser"):
    """Send a test password reset email using the actual template"""
    with app.app_context():
        try:
            print(f"\n📧 Sending password reset email to {recipient}...")
            
            # Read the reset password template
            template_path = os.path.join(os.path.dirname(__file__), 'templates', 'emails', 'reset_password.html')
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Replace placeholders with test data
            reset_url = "https://buymo.onrender.com/reset-password/test-token-12345"
            html_content = template_content.replace('{{ username }}', username)
            html_content = html_content.replace('{{ reset_url }}', reset_url)
            
            msg = Message(
                "🔐 Password Reset - BuyMo",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=[recipient]
            )
            msg.html = html_content
            
            mail.send(msg)
            print(f"✓ Password reset email sent successfully to {recipient}")
            return True
        except Exception as e:
            print(f"✗ Failed to send password reset email: {str(e)}")
            import traceback
            print(f"Traceback:\n{traceback.format_exc()}")
            return False

def main():
    """Main test function"""
    print("\n🧪 BuyMo Email Testing Script")
    print_config()
    
    # Check if password is set
    if not app.config['MAIL_PASSWORD']:
        print("❌ ERROR: MAIL_PASSWORD is not set in .env file")
        print("Please set MAIL_PASSWORD in your .env file and try again.")
        sys.exit(1)
    
    # Get recipient email
    if len(sys.argv) > 1:
        recipient = sys.argv[1]
    else:
        recipient = input("Enter recipient email address: ").strip()
    
    if not recipient:
        print("❌ ERROR: No recipient email provided")
        sys.exit(1)
    
    print(f"\nTesting emails to: {recipient}")
    print("-" * 60)
    
    # Run tests
    results = []
    
    print("\n1️⃣  Testing simple email...")
    results.append(("Simple Email", test_simple_email(recipient)))
    
    print("\n2️⃣  Testing welcome email...")
    results.append(("Welcome Email", test_welcome_email(recipient, "TestUser")))
    
    print("\n3️⃣  Testing order confirmation email...")
    results.append(("Order Confirmation", test_order_email(recipient)))
    
    print("\n4️⃣  Testing password reset email...")
    results.append(("Password Reset", test_reset_password_email(recipient, "TestUser")))
    
    # Print summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    for test_name, result in results:
        status = "✓ PASSED" if result else "✗ FAILED"
        print(f"{test_name:25} {status}")
    print("="*60 + "\n")
    
    # Exit with appropriate code
    if all(result for _, result in results):
        print("✅ All tests passed!")
        sys.exit(0)
    else:
        print("❌ Some tests failed. Check the logs above for details.")
        sys.exit(1)

if __name__ == "__main__":
    main()
