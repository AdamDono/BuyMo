from app import app, mail
from flask_mail import Message
import os

print("Testing Brevo Email...")
print(f"Server: {os.getenv('MAIL_SERVER')}")
print(f"Port: {os.getenv('MAIL_PORT')}")
print(f"User: {os.getenv('MAIL_USERNAME')}")

with app.app_context():
    try:
        msg = Message(
            "BuyMo Brevo Test",
            sender=app.config['MAIL_DEFAULT_SENDER'],
            recipients=["adamdono100@gmail.com"]
        )
        msg.body = "Testing email delivery via Brevo!"
        mail.send(msg)
        print("Brevo Email SUCCESS!")
    except Exception as e:
        print(f"Brevo Email FAILED: {e}")
