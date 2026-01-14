
import os

# 1. Safer Orders Route (fixes AttributeError)
orders_func = """@app.route('/orders')
@login_required
def orders():
    try:
        conn = database.get_db_connection()
        cur = conn.cursor()
        
        # 1. Fetch orders with all details explicitly
        cur.execute('''
            SELECT id, total_amount, status, order_date, tracking_number,
                   delivery_method, full_name, phone, street_address, suburb,
                   city, province, postal_code, delivery_fee, pickup_date,
                   driver_name, driver_phone, tracking_link, shipped_date,
                   estimated_delivery_date, delivered_at, proof_of_delivery, delivery_notes
            FROM orders 
            WHERE user_id = %s 
            ORDER BY order_date DESC
        ''', (current_user.id,))
        orders_data = cur.fetchall()
        
        # 2. Optimized: Fetch ALL items for ALL orders in one go (No N+1)
        order_ids = [o[0] for o in orders_data]
        all_items = {}
        if order_ids:
            cur.execute('''
                SELECT oi.order_id, p.name, p.image, oi.quantity, oi.price_at_purchase
                FROM order_items oi
                JOIN products p ON oi.product_id = p.id
                WHERE oi.order_id = ANY(%s);
            ''', (order_ids,))
            items_data = cur.fetchall()
            for item in items_data:
                oid = item[0]
                if oid not in all_items:
                    all_items[oid] = []
                all_items[oid].append({
                    'name': item[1], 
                    'image': item[2], 
                    'quantity': item[3], 
                    'price_at_purchase': float(item[4])
                })

        # 3. Build history objects using manual dict creation to avoid attribute errors
        # This completely bypasses the 'dict object has no attribute' error because we define the dict keys explicitly here.
        order_history = []
        for order in orders_data:
            order_id = order[0]
            # Handle potential None for order_date [3]
            order_date_str = 'N/A'
            if order[3]:
                try:
                   order_date_str = order[3].strftime('%Y-%m-%d %H:%M')
                except:
                   order_date_str = str(order[3])

            order_history.append({
                'id': order_id,
                'total_amount': float(order[1]),
                'status': order[2],
                'order_date': order[3], # Keep raw object for template filters if needed, or string
                'date': order_date_str, # used in some views?
                'tracking_number': order[4],
                'delivery_method': order[5],
                'full_name': order[6],
                'phone': order[7],
                'street_address': order[8],
                'suburb': order[9],
                'city': order[10],
                'province': order[11],
                'postal_code': order[12],
                'delivery_fee': float(order[13]) if order[13] else 0,
                'pickup_date': order[14],
                'driver_name': order[15],
                'driver_phone': order[16],
                'tracking_link': order[17],
                'shipped_date': order[18],
                'estimated_delivery_date': order[19],
                'delivered_at': order[20],
                'proof_of_delivery': order[21],
                'delivery_notes': order[22],
                'order_items': all_items.get(order_id, [])
            })

        cur.close()
        database.return_db_connection(conn)
        return render_template('orders.html', orders=order_history)
    except Exception as e:
        logger.error(f"Error fetching order history: {e}")
        return render_template('orders.html', orders=[])
"""

# 2. Add Toggle Coupon Route (missing)
toggle_coupon_func = """
@app.route('/admin/toggle-coupon/<int:coupon_id>', methods=['POST'])
@login_required
def toggle_coupon(coupon_id):
    if not current_user.is_admin:
        flash('Access denied.', 'error')
        return redirect(url_for('home'))
        
    conn = database.get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute('UPDATE coupons SET active = NOT active WHERE id = %s', (coupon_id,))
        conn.commit()
        flash('Coupon status updated.', 'success')
    except Exception as e:
        logger.error(f"Error toggling coupon: {e}")
        flash('Error updating coupon.', 'error')
    finally:
        cur.close()
        database.return_db_connection(conn)
    return redirect(url_for('admin_coupons'))
"""

with open('app.py', 'r') as f:
    lines = f.readlines()

# PATCH 1: Orders Function
# Find start of orders function
start_idx = -1
end_idx = -1
for i, line in enumerate(lines):
    if "@app.route('/orders')" in line:
        start_idx = i
        break

if start_idx != -1:
    # Find next route (e.g. admin/products)
    for i in range(start_idx + 1, len(lines)):
        if "@app.route" in lines[i]:
            end_idx = i
            break
    
    if end_idx != -1:
        # Replace
        lines[start_idx:end_idx] = [orders_func + "\n"]
        print("Replaced orders function.")
    else:
        print("Could not find end of orders function.")

# PATCH 2: Toggle Coupon
# Add it after delete_coupon route? Or just at the end of admin section?
# Search for delete_coupon
insert_idx = -1
for i, line in enumerate(lines):
    if "def delete_coupon" in line:
        # Find end of this function (look for next route or blank lines?)
        for j in range(i + 1, len(lines)):
            if "@app.route" in lines[j]:
                insert_idx = j
                break
        if insert_idx == -1: # Last function?
             insert_idx = len(lines)
        break

if insert_idx != -1:
    lines.insert(insert_idx, toggle_coupon_func + "\n")
    print("Added toggle_coupon route.")
else:
    print("Could not find place to insert toggle_coupon. Appending to end.")
    lines.append(toggle_coupon_func + "\n")

with open('app.py', 'w') as f:
    f.writelines(lines)
