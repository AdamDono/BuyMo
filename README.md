# BuyMo E-Commerce Platform

BuyMo is a full-featured e-commerce web application built with Python (Flask) and PostgreSQL. It offers a premium shopping experience with optimized performance, real-time stock management, and a comprehensive admin dashboard.

## 🚀 Features

### For Customers
*   **Fast Browsing**: Optimized with server-side caching and WebP image delivery for instant page loads.
*   **Product Discovery**: Search, filter by category, and price range.
*   **Wishlist**: Save items for later (persists across sessions).
*   **Shopping Cart**: Real-time stock checks and easy management.
*   **Checkout**: Integrated with PayFast for secure payments.
*   **Order Tracking**: Detailed order history with driver details, tracking links, and proof of delivery.
*   **Notifications**: Automated emails for welcome, order confirmation, and status updates.

### For Administrators
*   **Dashboard**: Real-time overview of sales, orders, and user stats.
*   **Product Management**: Add, edit, delete products with automatic image optimization (Cloudinary).
*   **Stock Control**: Inventory tracking with low-stock alerts.
*   **Order Fulfillment**: Manage order status, assign drivers, and upload proof of delivery.
*   **Coupons**: Create and manage discount codes.
*   **Database Management**: Built-in migration tools for schema updates.

## 🛠 Tech Stack

*   **Backend**: Python, Flask, Flask-Login, Flask-Mail.
*   **Database**: PostgreSQL (with psycopg2 connection pooling).
*   **Caching**: Flask-Caching (SimpleCache).
*   **Frontend**: HTML5, CSS3, JavaScript (Vanilla).
*   **Media**: Cloudinary (Image hosting & optimization).
*   **Deployment**: Ready for Render/Heroku (Gunicorn).

## ⚙️ Setup & Installation

1.  **Clone the repository**
    ```bash
    git clone https://github.com/yourusername/buymo.git
    cd buymo
    ```

2.  **Set up Virtual Environment**
    ```bash
    python3 -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install Dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Configure Environment Variables**
    Create a `.env` file in the root directory:
    ```ini
    # Database
    DATABASE_URL=postgresql://user:password@localhost:5432/ecom_db

    # Security
    SECRET_KEY=your_secure_secret_key

    # Cloudinary (Images)
    CLOUDINARY_CLOUD_NAME=your_cloud_name
    CLOUDINARY_API_KEY=your_api_key
    CLOUDINARY_API_SECRET=your_api_secret

    # Email (Gmail/SMTP)
    MAIL_SERVER=smtp.gmail.com
    MAIL_PORT=465
    MAIL_USE_SSL=True
    MAIL_USERNAME=your_email@gmail.com
    MAIL_PASSWORD=your_app_password
    MAIL_DEFAULT_SENDER=your_email@gmail.com
    ```

5.  **Run the Application**
    ```bash
    python3 app.py
    # OR using Gunicorn
    gunicorn app:app
    ```

## 📦 Deployment (Render)

The application includes a `Procfile` for seamless deployment on platforms like Render or Heroku. It automatically detects SSL requirements for cloud databases to ensure stable connections.
