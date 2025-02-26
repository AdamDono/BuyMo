from flask import Blueprint, render_template
from flask_login import login_required
from app.models import User, Product

admin_routes = Blueprint('admin_routes', __name__)

@admin_routes.route('/admin/dashboard')
@login_required
def admin_dashboard():
    # Fetch pending products for approval
    pending_products = Product.query.filter_by(status='pending').all()
    return render_template('admin_dashboard.html', pending_products=pending_products)

@admin_routes.route('/admin/approve_product/<int:product_id>')
@login_required
def approve_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.status = 'approved'
    db.session.commit()
    flash('Product approved!', 'success')
    return redirect(url_for('admin_routes.admin_dashboard'))

@admin_routes.route('/admin/reject_product/<int:product_id>')
@login_required
def reject_product(product_id):
    product = Product.query.get_or_404(product_id)
    product.status = 'rejected'
    db.session.commit()
    flash('Product rejected!', 'error')
    return redirect(url_for('admin_routes.admin_dashboard'))