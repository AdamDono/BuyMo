
import os

# Using triple double quotes for outer string since inner code uses triple single quotes
new_code = """@app.route('/payfast/notify', methods=['POST'])
def payfast_notify():
    \"\"\"
    PayFast ITN handler - MUST respond within 10 seconds to avoid 502 errors
    We respond immediately, then process the order in background
    \"\"\"
    logger.info("=" * 60)
    logger.info("PayFast ITN received")
    
    # Quick validation
    if request.form.get('payment_status') != 'COMPLETE':
        logger.warning(f"Payment not complete: {request.form.get('payment_status')}")
        return "Payment not complete", 200
    
    pending_order_id = request.form.get('m_payment_id')
    user_id_str = request.form.get('custom_int1')
    
    if not pending_order_id or not user_id_str:
        logger.error("Missing required fields")
        return "Missing fields", 400
    
    try:
        user_id = int(user_id_str)
    except ValueError:
        logger.error(f"Invalid user_id: {user_id_str}")
        return "Invalid user_id", 400
    
    # Capture app for thread
    app_ctx = app
    
    # Process order in background thread to respond quickly
    def process_order_background(app_instance, p_order_id, u_id):
        \"\"\"Background processing with robust error handling and logging\"\"\"
        try:
            # Use app context necessary for render_template (emails)
            with app_instance.app_context():
                
                # Setup local file logging for debug
                def file_log(msg):
                    try:
                        from datetime import datetime
                        with open('itn_debug.log', 'a') as f:
                            f.write(f"{datetime.now()} - {msg}\\n")
                        print(f"ITN: {msg}") # Also to stdout
                    except: pass
                
                file_log(f"STARTING processing for Order {p_order_id} User {u_id}")
                
                max_retries = 2
                for attempt in range(max_retries):
                    conn = None
                    try:
                        file_log(f"Attempt {attempt + 1}")
                        conn = database.get_db_connection()
                        cur = conn.cursor()

                        # 1. Get Pending Order
                        cur.execute('''
                            SELECT user_id, total_amount, cart_items_json, delivery_info_json
                            FROM pending_orders
                            WHERE id = %s
                        ''', (p_order_id,))
                        pending_order = cur.fetchone()

                        if not pending_order:
                            file_log("Pending order not found")
                            database.return_db_connection(conn)
                            return

                        if pending_order[0] != u_id:
                            file_log(f"User mismatch: PO User {pending_order[0]} != {u_id}")
                            database.return_db_connection(conn)
                            return

                        total_amount = pending_order[1]
                        import json
                        cart_items = json.loads(pending_order[2])
                        # Handle potential missing/null delivery info
                        delivery_info = {}
                        if len(pending_order) > 3 and pending_order[3]:
                            delivery_info = json.loads(pending_order[3])

                        # 2. Stock Validation
                        for item in cart_items:
                            cur.execute('SELECT remaining_quantity FROM products WHERE id = %s', (item['product_id'],))
                            res = cur.fetchone()
                            remaining = res[0] if res else 0
                            if remaining < item['quantity']:
                                file_log(f"Stock check failed for Product {item['product_id']}")
                                database.return_db_connection(conn)
                                return

                        # 3. Create Order
                        tracking_number = generate_tracking_number()
                        
                        cur.execute('''
                            INSERT INTO orders (
                                user_id, tracking_number, total_amount, delivery_method, full_name, phone,
                                street_address, suburb, city, province, postal_code,
                                delivery_fee, pickup_date, status
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 'processing')
                            RETURNING id
                        ''', (
                            u_id, tracking_number, total_amount,
                            delivery_info.get('delivery_method', 'delivery'),
                            delivery_info.get('full_name'),
                            delivery_info.get('phone'),
                            delivery_info.get('street_address'),
                            delivery_info.get('suburb'),
                            delivery_info.get('city'),
                            delivery_info.get('province'),
                            delivery_info.get('postal_code'),
                            delivery_info.get('delivery_fee', 0),
                            delivery_info.get('pickup_date')
                        ))
                        order_id = cur.fetchone()[0]
                        file_log(f"Created Order #{order_id}")

                        # 4. Add Items
                        for item in cart_items:
                            cur.execute('''
                                INSERT INTO order_items (order_id, product_id, quantity, price_at_purchase)
                                VALUES (%s, %s, %s, %s)
                            ''', (order_id, item['product_id'], item['quantity'], item['price']))

                        # 5. Update Stock
                        for item in cart_items:
                            cur.execute('''
                                UPDATE products 
                                SET remaining_quantity = remaining_quantity - %s
                                WHERE id = %s
                            ''', (item['quantity'], item['product_id']))

                        # 6. Clean Up
                        cur.execute('DELETE FROM cart_items WHERE user_id = %s', (u_id,))
                        cur.execute('DELETE FROM pending_orders WHERE id = %s', (p_order_id,))

                        # 7. COMMIT
                        conn.commit()
                        file_log("COMMIT SUCCESSFUL")

                        # 8. Send Email (After commit)
                        try:
                            user_data = database.get_user_by_id(u_id)
                            if user_data:
                                email_details = {
                                    'order_id': order_id,
                                    'tracking_number': tracking_number,
                                    'total_amount': float(total_amount),
                                    'full_name': delivery_info.get('full_name', user_data[1]),
                                    'delivery_method': delivery_info.get('delivery_method', 'delivery'),
                                    'items_count': len(cart_items)
                                }
                                file_log(f"Sending email to {user_data[2]}...")
                                send_order_email(user_data[2], email_details)
                                file_log("Email sent function called")
                        except Exception as email_err:
                            file_log(f"Email Error: {str(email_err)}")
                        
                        database.return_db_connection(conn)
                        return

                    except Exception as e:
                        file_log(f"DB Error Attempt {attempt}: {str(e)}")
                        if conn:
                            conn.rollback()
                            database.return_db_connection(conn)
                        
                        if attempt < max_retries - 1:
                            database.close_pool()
                            continue
        except Exception as outer_e:
            print(f"CRITICAL BG THREAD ERROR: {str(outer_e)}")

    # Start background thread
    from threading import Thread
    thread = Thread(target=process_order_background, args=(app_ctx, pending_order_id, user_id))
    thread.daemon = True
    thread.start()
    
    # Respond IMMEDIATELY to PayFast (within 1 second)
    logger.info("Responding OK to PayFast immediately")
    return "OK", 200

"""

with open('app.py', 'r') as f:
    lines = f.readlines()

start_line = 1242
end_line = 1424

# Verify targets (0-indexed)
# Checking roughly to ensure we are in the right place
# Line 1242 is @app.route... (index 1241 in list? No, line 1 is index 0)
# Step 240 output: 1424 is @app.route...
# Step 237 output: 1242 is @app.route...
# In list, index = line_num - 1.
start_idx = 1242 - 1
end_idx = 1424 - 1

if '@app.route' not in lines[start_idx] and 'payfast_notify' not in lines[start_idx+1]:
    print("FAILED: Could not find start line")
    print(f"Line {start_idx}: {lines[start_idx]}")
    exit(1)

if 'remove-from-cart' not in lines[end_idx]:
    print("FAILED: Could not find end line")
    print(f"Line {end_idx}: {lines[end_idx]}")
    print(f"Expected remove-from-cart, found: {lines[end_idx]}")
    # Search for it?
    found = False
    for i in range(end_idx - 5, end_idx + 5):
        if 'remove-from-cart' in lines[i]:
            print(f"Found it at {i}. Adjusting.")
            end_idx = i
            found = True
            break
    if not found:
        exit(1)

# Replace
lines[start_idx:end_idx] = [new_code] # Inject single string block

with open('app.py', 'w') as f:
    f.writelines(lines)

print("SUCCESS: app.py patched")
