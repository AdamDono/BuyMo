from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints (routes)
    from app.routes import main_routes  # Import main_routes from routes.py
    from app.auth import auth_routes    # Import auth_routes from auth.py
    app.register_blueprint(main_routes)
    app.register_blueprint(auth_routes)

    return app