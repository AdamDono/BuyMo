from flask import Blueprint, render_template
from flask_login import login_required

# Create a Blueprint for main routes
main_routes = Blueprint('main_routes', __name__)

@main_routes.route('/')
def index():
    return render_template('index.html')

@main_routes.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')