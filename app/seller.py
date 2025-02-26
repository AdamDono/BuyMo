from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app.models import Product

seller_routes = Blueprint('seller_routes', __name__)

@seller_routes.route('/seller/dashboard')
@login_required
def seller_dashboard():
    # Fetch products added by the current seller
    seller_products = Product.query.filter_by(seller_id=current_user.id).all()
    return render_template('seller_dashboard.html', seller_products=seller_products)

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