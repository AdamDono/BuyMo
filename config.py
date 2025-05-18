import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key'
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'postgresql://postgres:Fliph106@localhost:5433/ecommerce_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    MAIL_SERVER = 'smtp.gmail.com'  # Use your SMTP provider
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')  # Store in env vars
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')  # Store in env vars
    MAIL_DEFAULT_SENDER = 'noreply@buymo.com'