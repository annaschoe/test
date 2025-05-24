"""
Routes for the festival logistics application
"""

from flask import render_template, request, redirect, flash, url_for, session
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import logging
import time
import os
import sys
import sqlite3
from flask_wtf.csrf import CSRFError

def register_routes(app):
    """
    Register all routes with the Flask app.
    This function-based approach eliminates circular imports.
    
    Args:
        app: The Flask application instance
    """
    # Import User directly to avoid circular imports
    from app import User, limiter
    from database import get_db, log_event
    
    # 1. Basic navigation routes
    @app.route('/')
    def index():
        """Redirect to login or dashboard"""
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        return redirect(url_for('login'))

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        """Handle user registration"""
        # Check if already logged in
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            location_name = request.form.get('location_name')

            # Basic validation
            if not username or not password or not confirm_password or not location_name:
                flash('All fields are required', 'error')
                return render_template('register.html', username=username, location_name=location_name)

            if password != confirm_password:
                flash('Passwords do not match', 'error')
                return render_template('register.html', username=username, location_name=location_name)

            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    # Check if username already exists
                    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                    if cursor.fetchone():
                        flash('Username already exists', 'error')
                        return render_template('register.html', username=username, location_name=location_name)

                    # Check if users table has the correct columns
                    cursor.execute("PRAGMA table_info(users)")
                    columns = [row[1] for row in cursor.fetchall()]
                    required_columns = {'username', 'password', 'location_name'}
                    if not required_columns.issubset(set(columns)):
                        app.logger.error(f"Users table missing columns: {required_columns - set(columns)}")
                        flash('Internal error: users table misconfigured. Contact admin.', 'error')
                        return render_template('register.html', username=username, location_name=location_name)

                    # Create new user - fixed hashing method to use pbkdf2:sha256 instead of sha256
                    hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
                    cursor.execute(
                        "INSERT INTO users (username, password, location_name) VALUES (?, ?, ?)",
                        (username, hashed_password, location_name)
                    )
                    user_id = cursor.lastrowid
                    # Log registration event in the same transaction
                    cursor.execute(
                        "INSERT INTO event_logs (user_id, username, action_type, entity_type, details) VALUES (?, ?, ?, ?, ?)",
                        (user_id, username, 'register', 'user', f'Registered new user: {username} at {location_name}')
                    )
                    conn.commit()
                    flash('Registration successful! Please log in.', 'success')
                    return redirect(url_for('login'))
            except Exception as e:
                app.logger.error(f"Registration error: {str(e)}", exc_info=True)
                flash('An error occurred during registration. Please try again.', 'error')
                return render_template('register.html', username=username, location_name=location_name)
        
        return render_template('register.html')

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """Handle user login"""
        # Check if already logged in
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            # Basic validation
            if not username or not password:
                flash('Please enter both username and password', 'error')
                return render_template('login.html')
            
            try:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                    user = cursor.fetchone()
                    
                    if not user:
                        flash('Invalid username or password', 'error')
                        return render_template('login.html')
                    
                    # Added debugging
                    app.logger.info(f"Login attempt for user {username}, ID: {user['id']}")
                    
                    # Get hash info for debugging
                    hash_info = user['password'].split('$', 2)[0] if '$' in user['password'] else 'unknown'
                    app.logger.info(f"Password hash method: {hash_info}")
                    
                    # Check password
                    if check_password_hash(user['password'], password):
                        # Get user ID for debugging
                        app.logger.info(f"Password check successful, user ID: {user['id']}")
                        
                        # Create user object and log in
                        user_obj = User(user['id'], user['username'], user['location_name'])
                        login_user(user_obj, remember=True)
                        
                        app.logger.info(f"User logged in successfully: {user['username']}")
                        
                        # Redirect
                        next_page = request.args.get('next', url_for('dashboard'))
                        return redirect(next_page)
                    else:
                        app.logger.warning(f"Password check failed for user: {username}")
                        flash('Invalid username or password', 'error')
            except Exception as e:
                app.logger.error(f"Login error: {str(e)}", exc_info=True)
                flash('An error occurred during login. Please try again.', 'error')
        
        # Count users to check if registration should be allowed
        user_count = 0
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
        except Exception as e:
            app.logger.error(f"Error counting users: {str(e)}")
        
        return render_template('login.html', user_count=user_count)

    @app.route('/dashboard')
    @login_required
    def dashboard():
        """User dashboard with inventory visualization"""
        # Get inventory stats for the charts
        inventory_stats = {
            'by_location': [],
            'by_type': [],
            'total_items': 0,
            'total_transfers': 0
        }
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Get inventory by location - MODIFIED to filter only locations the current user has transferred to/from
                cursor.execute("""
                    SELECT u.location_name, SUM(i.quantity) as total
                    FROM inventory i
                    JOIN users u ON i.location_id = u.id
                    WHERE i.location_id = ? OR i.location_id IN (
                        -- Get locations user has received from
                        SELECT DISTINCT from_location_id FROM transfers WHERE to_location_id = ?
                        UNION
                        -- Get locations user has sent to
                        SELECT DISTINCT to_location_id FROM transfers WHERE from_location_id = ?
                    )
                    GROUP BY u.location_name
                    ORDER BY total DESC
                """, (current_user.id, current_user.id, current_user.id))
                inventory_stats['by_location'] = [dict(row) for row in cursor.fetchall()]
                
                # Get inventory by type - MODIFIED to only show current user's inventory
                cursor.execute("""
                    SELECT type, SUM(quantity) as total
                    FROM inventory
                    WHERE location_id = ?
                    GROUP BY type
                    ORDER BY total DESC
                """, (current_user.id,))
                inventory_stats['by_type'] = [dict(row) for row in cursor.fetchall()]
                
                # Get total items for current user only
                cursor.execute("SELECT SUM(quantity) FROM inventory WHERE location_id = ?", (current_user.id,))
                result = cursor.fetchone()
                inventory_stats['total_items'] = result[0] if result and result[0] else 0
                
                # Get total transfers involving the current user
                cursor.execute("""
                    SELECT COUNT(*) FROM transfers 
                    WHERE from_location_id = ? OR to_location_id = ?
                """, (current_user.id, current_user.id))
                result = cursor.fetchone()
                inventory_stats['total_transfers'] = result[0] if result and result[0] else 0
                
                # Get user's recent activity (transfers)
                cursor.execute("""
                    SELECT t.timestamp, u.location_name as to_location, i.name, t.quantity
                    FROM transfers t
                    JOIN users u ON t.to_location_id = u.id
                    JOIN inventory i ON t.item_id = i.id
                    WHERE t.from_location_id = ?
                    ORDER BY t.timestamp DESC
                    LIMIT 5
                """, (current_user.id,))
                recent_activity = cursor.fetchall()
                
                # Get recently added inventory items
                cursor.execute("""
                    SELECT i.id, i.name, i.quantity, i.type, i.timestamp,
                           u.location_name
                    FROM inventory i
                    JOIN users u ON i.location_id = u.id
                    WHERE i.location_id = ?
                    ORDER BY i.timestamp DESC
                    LIMIT 5
                """, (current_user.id,))
                inventory_items = cursor.fetchall()
        except Exception as e:
            app.logger.error(f"Error fetching dashboard data: {str(e)}")
            flash("Could not load dashboard statistics", "error")
            recent_activity = []
            inventory_items = []
        
        return render_template('dashboard.html', 
                              stats=inventory_stats,
                              recent_activity=recent_activity,
                              inventory_items=inventory_items)

    # 2. Inventory management routes
    @app.route('/inventory', methods=['GET', 'POST'])
    @login_required
    def inventory():
        """Handle inventory management"""
        # Handle POST request for adding/editing items
        if request.method == 'POST':
            try:
                name = request.form.get('name')
                quantity = request.form.get('quantity')
                item_type = request.form.get('type')
                item_id = request.form.get('item_id')  # For editing existing items
                
                # Validate form data
                if not name or not quantity or not item_type:
                    flash('All fields are required', 'error')
                else:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        if item_id:  # Update existing item
                            cursor.execute(
                                "UPDATE inventory SET name=?, quantity=?, type=? WHERE id=? AND location_id=?",
                                (name, quantity, item_type, item_id, current_user.id)
                            )
                            flash('Item updated successfully', 'success')
                        else:  # Add new item
                            cursor.execute(
                                "INSERT INTO inventory (name, quantity, type, location_id) VALUES (?, ?, ?, ?)",
                                (name, quantity, item_type, current_user.id)
                            )
                            flash('Item added successfully', 'success')
                        conn.commit()
            except Exception as e:
                app.logger.error(f"Error adding/updating inventory: {str(e)}")
                flash('An error occurred while processing your request', 'error')
        
        # GET request handling (existing code)
        items = []
        locations = []
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM inventory 
                    WHERE location_id = ? 
                    ORDER BY name
                """, (current_user.id,))
                items = cursor.fetchall()
                
                # Get all other locations for transfers
                cursor.execute("""
                    SELECT id, location_name 
                    FROM users 
                    WHERE id != ?
                """, (current_user.id,))
                locations = cursor.fetchall()
        except Exception as e:
            app.logger.error(f"Error fetching inventory: {str(e)}")
            flash("Could not load inventory items", "error")
        
        return render_template('inventory.html', items=items, locations=locations)

    @app.route('/transfer-item', methods=['POST'])
    @login_required
    def transfer_item():
        """Handle item transfer between locations"""
        try:
            item_id = request.form.get('item_id', type=int)
            to_location_id = request.form.get('to_location', type=int)
            quantity = request.form.get('quantity', type=int)
            
            # Add more detailed logging
            app.logger.info(f"Transfer requested: Item ID {item_id}, To Location {to_location_id}, Quantity {quantity}")
            
            # Basic validation
            if not item_id or not to_location_id or not quantity or quantity < 1:
                flash('All fields are required and quantity must be at least 1', 'error')
                return redirect(url_for('inventory'))
                
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Check if item exists and belongs to current user
                cursor.execute("""
                    SELECT * FROM inventory 
                    WHERE id = ? AND location_id = ?
                """, (item_id, current_user.id))
                item = cursor.fetchone()
                
                if not item:
                    app.logger.error(f"Item not found or user doesn't have permission: Item ID {item_id}, User ID {current_user.id}")
                    flash('Item not found or you do not have permission', 'error')
                    return redirect(url_for('inventory'))
                    
                # Check if quantity is valid
                if item['quantity'] < quantity:
                    app.logger.warning(f"Insufficient quantity: Available {item['quantity']}, Requested {quantity}")
                    flash(f'You only have {item["quantity"]} items available', 'error')
                    return redirect(url_for('inventory'))
                    
                # Check if destination location exists
                cursor.execute("SELECT * FROM users WHERE id = ?", (to_location_id,))
                to_location = cursor.fetchone()
                
                if not to_location:
                    app.logger.error(f"Destination location not found: ID {to_location_id}")
                    flash('Destination location not found', 'error')
                    return redirect(url_for('inventory'))
                    
                # Generate transfer tag
                transfer_tag = f'TRF-{int(time.time())}'
                app.logger.info(f"Generated transfer tag: {transfer_tag}")
                    
                # Create transfer record
                cursor.execute("""
                    INSERT INTO transfers 
                    (from_location_id, to_location_id, item_id, quantity, transfer_tag) 
                    VALUES (?, ?, ?, ?, ?)
                """, (current_user.id, to_location_id, item_id, quantity, transfer_tag))
                
                # Deduct from sender's inventory
                cursor.execute("""
                    UPDATE inventory 
                    SET quantity = quantity - ? 
                    WHERE id = ?
                """, (quantity, item_id))
                
                # Check if the item already exists in receiver's inventory
                cursor.execute("""
                    SELECT * FROM inventory 
                    WHERE name = ? AND type = ? AND location_id = ?
                """, (item['name'], item['type'], to_location_id))
                receiver_item = cursor.fetchone()
                
                if receiver_item:
                    # Update existing item quantity in receiver's inventory
                    app.logger.info(f"Updating existing item in receiver inventory: ID {receiver_item['id']}")
                    cursor.execute("""
                        UPDATE inventory 
                        SET quantity = quantity + ?, transfer_tag = ? 
                        WHERE id = ?
                    """, (quantity, transfer_tag, receiver_item['id']))
                else:
                    # Create new item in receiver's inventory
                    app.logger.info(f"Creating new item in receiver inventory: Name {item['name']}, Type {item['type']}")
                    cursor.execute("""
                        INSERT INTO inventory 
                        (name, quantity, type, location_id, transfer_tag) 
                        VALUES (?, ?, ?, ?, ?)
                    """, (item['name'], quantity, item['type'], to_location_id, transfer_tag))
                    
                # Verify the item was created/updated in the receiver's inventory
                cursor.execute("""
                    SELECT * FROM inventory 
                    WHERE name = ? AND type = ? AND location_id = ?
                """, (item['name'], item['type'], to_location_id))
                verify_item = cursor.fetchone()
                
                if verify_item:
                    app.logger.info(f"Verification successful: Item exists in receiver inventory with ID {verify_item['id']} and quantity {verify_item['quantity']}")
                else:
                    app.logger.error(f"Verification failed: Item not found in receiver inventory after transfer!")
                    
                # Log the event
                log_event(
                    current_user.id,
                    current_user.username,
                    'transfer',
                    'inventory',
                    item_id,
                    f"Transferred {quantity} {item['name']} from {current_user.location_name} to {to_location['location_name']}"
                )
                
                conn.commit()  # to record the transfer
                flash(f'Successfully transferred {quantity} {item["name"]} to {to_location["location_name"]}', 'success')
        except Exception as e:
            app.logger.error(f"Error transferring item: {e}", exc_info=True)
            flash('An error occurred during the transfer', 'error')
        return redirect(url_for('inventory'))

    @app.route('/inventory/delete/<int:item_id>', methods=['POST'])
    @login_required
    def delete_item(item_id):
        """Delete an inventory item"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                # First check if the item exists and belongs to the current user
                cursor.execute(
                    "SELECT * FROM inventory WHERE id = ? AND location_id = ?", 
                    (item_id, current_user.id)
                )
                item = cursor.fetchone()

                if not item:
                    flash('Item not found or you do not have permission to delete it', 'error')
                    return redirect(url_for('inventory'))

                # Check if the item is referenced in the transfers table
                cursor.execute(
                    """
                    SELECT COUNT(*) FROM transfers 
                    WHERE item_id = ?
                    """, 
                    (item_id,)
                )
                transfer_count = cursor.fetchone()[0]

                if transfer_count > 0:
                    flash('Cannot delete this item because it is referenced in transfer records. Remove the transfers first.', 'error')
                    return redirect(url_for('inventory'))

                # Delete the item if not referenced and log in the same transaction
                cursor.execute(
                    "DELETE FROM inventory WHERE id = ?", 
                    (item_id,)
                )
                cursor.execute(
                    "INSERT INTO event_logs (user_id, username, action_type, entity_type, item_id, details) VALUES (?, ?, ?, ?, ?, ?)",
                    (current_user.id, current_user.username, 'delete', 'inventory', item_id, f"Deleted item: {item['name']} (quantity: {item['quantity']}, type: {item['type']})")
                )
                conn.commit()
                flash('Item deleted successfully', 'success')
        except Exception as e:
            app.logger.error(f"Error deleting inventory item: {e}")
            flash('An error occurred while deleting the item', 'error')
        
        return redirect(url_for('inventory'))
        
    @app.route('/items/edit/<int:item_id>', methods=['GET', 'POST'])
    @login_required
    def edit_item(item_id):
        """Edit an existing inventory item"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, name, quantity, type
                    FROM inventory
                    WHERE id = ? AND location_id = ?
                """, (item_id, current_user.id))
                item = cursor.fetchone()

                if not item:
                    flash('Item not found or you do not have permission', 'error')
                    return redirect(url_for('inventory'))

                if request.method == 'POST':
                    name = request.form.get('name')
                    quantity = request.form.get('quantity', type=int)
                    item_type = request.form.get('type')

                    if not name or quantity is None or not item_type:
                        flash('All fields are required', 'error')
                        return render_template('edit.html', item=item)

                    # Update and log in the same transaction
                    cursor.execute("""
                        UPDATE inventory
                        SET name = ?, quantity = ?, type = ?
                        WHERE id = ? AND location_id = ?
                    """, (name, quantity, item_type, item_id, current_user.id))
                    cursor.execute(
                        "INSERT INTO event_logs (user_id, username, action_type, entity_type, item_id, details) VALUES (?, ?, ?, ?, ?, ?)",
                        (current_user.id, current_user.username, 'edit', 'inventory', item_id, f'Edited item: {name} (quantity: {quantity}, type: {item_type})')
                    )
                    conn.commit()

                    flash('Item updated successfully', 'success')
                    return redirect(url_for('inventory'))
        except Exception as e:
            app.logger.error(f"Error editing item: {e}")
            flash('Error updating item', 'error')
        # These are the commonly used types that should match what's in inventory.html
        item_types = ["Glass", "Plastic", "Metal", "Other"]
        return render_template('edit.html', item=item, item_types=item_types)
                    
    @app.route('/items/add', methods=['GET', 'POST'])
    @login_required
    def add_item():
        """Add new inventory item"""
        if request.method == 'POST':
            try:
                name = request.form.get('name')
                quantity = request.form.get('quantity', type=int)
                item_type = request.form.get('type')

                if not name or quantity is None or not item_type:
                    flash('All fields are required', 'error')
                    return render_template('add_item.html', item_types=app.config['ITEM_TYPES'])

                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT INTO inventory (name, quantity, type, location_id)
                        VALUES (?, ?, ?, ?)
                    """, (name, quantity, item_type, current_user.id))
                    item_id = cursor.lastrowid

                    # Directly insert event log in the same transaction for speed
                    cursor.execute(
                        "INSERT INTO event_logs (user_id, username, action_type, entity_type, item_id, details) VALUES (?, ?, ?, ?, ?, ?)",
                        (current_user.id, current_user.username, 'create', 'inventory', item_id, f"Created new item: {name} (quantity: {quantity}, type: {item_type})")
                    )
                    conn.commit()

                flash('Item added successfully', 'success')
                return redirect(url_for('dashboard'))
            except Exception as e:
                logging.error(f"Error adding item: {e}")
                flash('Error adding item', 'error')
        
        # Fixed: Use available item types if ITEM_TYPES doesn't exist in config
        item_types = app.config.get('ITEM_TYPES', ["Glass", "Plastic", "Metal", "Other"])
        return render_template('add_item.html', item_types=item_types)

    @app.route('/items/increase/<int:item_id>', methods=['POST'])
    @login_required
    def increase_item(item_id):
        """Increase inventory item quantity"""
        try:
            quantity = request.form.get('quantity', type=int)
            
            # Basic validation
            if not quantity or quantity <= 0:
                flash('Please enter a valid quantity greater than 0', 'error')
                return redirect(url_for('inventory'))
            
            # Get item details first to avoid locking issues
            item = None
            current_quantity = 0
            item_name = ""
            
            # Get the item details first in a separate connection
            with get_db() as conn:
                cursor = conn.cursor()
                # Get item details
                cursor.execute("""
                    SELECT id, name, quantity as current_quantity FROM inventory
                    WHERE id = ? AND location_id = ?
                """, (item_id, current_user.id))
                item = cursor.fetchone()
                
                if not item:
                    flash('Item not found or you do not have permission', 'error')
                    return redirect(url_for('inventory'))
                
                item_name = item['name']
                current_quantity = item['current_quantity']
            
            # Now perform the update in a separate connection to reduce lock time
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        # Update quantity
                        cursor.execute("""
                            UPDATE inventory
                            SET quantity = quantity + ?
                            WHERE id = ? AND location_id = ?
                        """, (quantity, item_id, current_user.id))
                        
                        conn.commit()
                        success = True
                except sqlite3.OperationalError as sql_error:
                    if 'database is locked' in str(sql_error) and retry_count < max_retries - 1:
                        retry_count += 1
                        app.logger.warning(f"Database lock detected, retrying (attempt {retry_count}/{max_retries})...")
                        time.sleep(0.5)  # Brief pause before retry
                    else:
                        raise
            
            # Log the event in a separate connection to avoid locks
            if success:
                try:
                    log_event(
                        current_user.id,
                        current_user.username,
                        'increase',
                        'inventory',
                        item_id,
                        f"Increased {item_name} quantity by {quantity} (from {current_quantity} to {current_quantity + quantity})"
                    )
                    flash(f"Successfully increased {item_name} quantity by {quantity}", 'success')
                except Exception as log_error:
                    app.logger.error(f"Error logging event: {log_error}")
                    # Continue even if logging failed, update was successful
                    flash(f"Quantity updated, but event logging failed.", 'warning')
        except Exception as e:
            app.logger.error(f"Error increasing inventory: {e}")
            flash('An error occurred while updating inventory', 'error')
        
        return redirect(url_for('inventory'))

    @app.route('/items/reduce/<int:item_id>', methods=['POST'])
    @login_required
    def reduce_item(item_id):
        """Reduce inventory item quantity"""
        try:
            quantity = request.form.get('quantity', type=int)

            if not quantity or quantity <= 0:
                flash('Please enter a valid quantity greater than 0', 'error')
                return redirect(url_for('inventory'))

            # Get item details first to avoid locking issues
            item = None
            current_quantity = 0
            item_name = ""
            
            # Get the item details first in a separate connection
            with get_db() as conn:
                cursor = conn.cursor()
                # Get item details
                cursor.execute("""
                    SELECT id, name, quantity as current_quantity FROM inventory
                    WHERE id = ? AND location_id = ?
                """, (item_id, current_user.id))
                item = cursor.fetchone()
                
                if not item:
                    flash('Item not found or you do not have permission', 'error')
                    return redirect(url_for('inventory'))
                
                item_name = item['name']
                current_quantity = item['current_quantity']
                
                # Check if we have enough quantity
                if current_quantity < quantity:
                    flash(f"Cannot reduce by {quantity}, only {current_quantity} available", 'error')
                    return redirect(url_for('inventory'))
            
            # Now perform the update in a separate connection to reduce lock time
            max_retries = 3
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    with get_db() as conn:
                        cursor = conn.cursor()
                        # Update quantity
                        cursor.execute("""
                            UPDATE inventory
                            SET quantity = quantity - ?
                            WHERE id = ? AND location_id = ?
                        """, (quantity, item_id, current_user.id))
                        
                        conn.commit()
                        success = True
                except sqlite3.OperationalError as sql_error:
                    if 'database is locked' in str(sql_error) and retry_count < max_retries - 1:
                        retry_count += 1
                        app.logger.warning(f"Database lock detected, retrying (attempt {retry_count}/{max_retries})...")
                        time.sleep(0.5)  # Brief pause before retry
                    else:
                        raise
            
            # Log the event in a separate connection to avoid locks
            if success:
                try:
                    log_event(
                        current_user.id,
                        current_user.username,
                        'reduce',
                        'inventory',
                        item_id,
                        f"Reduced {item_name} quantity by {quantity} (from {current_quantity} to {current_quantity - quantity})"
                    )
                    flash(f"Successfully reduced {item_name} quantity by {quantity}", 'success')
                except Exception as log_error:
                    app.logger.error(f"Error logging event: {log_error}")
                    # Continue even if logging failed, update was successful
                    flash(f"Quantity updated, but event logging failed.", 'warning')
        except Exception as e:
            app.logger.error(f"Error reducing inventory: {e}")
            flash('An error occurred while updating inventory', 'error')
        
        return redirect(url_for('inventory'))

    # 3. Transfer management routes
    @app.route('/transfers')
    @login_required
    def transfers():
        """Handle transfer history view"""
        transfers_sent = []
        transfers_received = []
        # Get transfers sent by this user
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                # Get transfers sent by this user
                cursor.execute("""
                    SELECT t.*, u.location_name as to_location, i.name as item_name
                    FROM transfers t
                    JOIN users u ON t.to_location_id = u.id
                    JOIN inventory i ON t.item_id = i.id
                    WHERE t.from_location_id = ?
                    ORDER BY t.timestamp DESC
                """, (current_user.id,))
                transfers_sent = cursor.fetchall()
                
                # Get transfers received by this user
                cursor.execute("""
                    SELECT t.*, u.location_name as from_location, i.name as item_name
                    FROM transfers t
                    JOIN users u ON t.from_location_id = u.id
                    JOIN inventory i ON t.item_id = i.id
                    WHERE t.to_location_id = ?
                    ORDER BY t.timestamp DESC
                """, (current_user.id,))
                transfers_received = cursor.fetchall()
        except Exception as e:
            app.logger.error(f"Error fetching transfers: {str(e)}")
            flash("Could not load transfer history", "error")
        
        return render_template('transfers.html', 
                              transfers_sent=transfers_sent,    
                              transfers_received=transfers_received)

    @app.route('/transfers/delete/<int:transfer_id>', methods=['POST'])
    @login_required
    def delete_transfer(transfer_id):
        """Delete a transfer record"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # First verify the transfer exists and belongs to the current user
                cursor.execute("""
                    SELECT t.*, i.quantity as current_quantity, i.id as inventory_id
                    FROM transfers t
                    JOIN inventory i ON t.item_id = i.id
                    WHERE t.id = ? AND (t.from_location_id = ? OR t.to_location_id = ?)
                """, (transfer_id, current_user.id, current_user.id))
                transfer = cursor.fetchone()
                
                if not transfer:
                    flash('Transfer record not found or you do not have permission to delete it', 'error')
                    return redirect(url_for('transfers'))
                    
                # Handle inventory updates based on whether user is sender or receiver
                if transfer['from_location_id'] == current_user.id:
                    # User is the sender - add the quantity back to their inventory
                    cursor.execute("""
                        UPDATE inventory
                        SET quantity = quantity + ?
                        WHERE id = ? AND location_id = ?
                    """, (transfer['quantity'], transfer['item_id'], current_user.id))
                        
                elif transfer['to_location_id'] == current_user.id:
                    # User is the receiver - remove the quantity from their inventory
                    # Make sure we don't go below 0
                    cursor.execute("""
                        UPDATE inventory
                        SET quantity = MAX(0, quantity - ?)
                        WHERE id = ? AND location_id = ?
                    """, (transfer['quantity'], transfer['item_id'], current_user.id))
                
                # Log the event
                log_event(
                    current_user.id,
                    current_user.username,
                    'delete',
                    'transfer',
                    transfer_id,
                    f"Deleted transfer of {transfer['quantity']} item(s) {transfer.get('item_name', 'unknown')} " + 
                    (f"from {current_user.location_name}" if transfer['from_location_id'] == current_user.id else 
                     f"to {current_user.location_name}")
                )
                
                # Now delete the transfer record
                cursor.execute("DELETE FROM transfers WHERE id = ?", (transfer_id,))
                conn.commit()
                flash('Transfer record deleted successfully', 'success')
                
        except Exception as e:
            app.logger.error(f"Error deleting transfer: {e}")
            flash('An error occurred while deleting the transfer record', 'error')
        
        return redirect(url_for('transfers'))

    # 4. User management routes
    @app.route('/logout')
    @login_required
    def logout():
        """Handle user logout"""
        flash('You have been logged out successfully', 'success')
        logout_user()
        return redirect(url_for('login'))

    # 5. Utility/diagnostic routes
    @app.route('/browser-check')
    def browser_check():
        user_agent = request.headers.get('User-Agent', '')
        is_mobile = 'Mobile' in user_agent or 'Android' in user_agent
        return render_template('browser_check.html',
                              user_agent=user_agent,
                              is_mobile=is_mobile)

    @app.route('/test')
    def test_route():
        """Show the current IP address of the client"""
        return "Server is running! Connection successful."

    @app.route('/ip')
    def show_ip():
        client_ip = request.remote_addr
        return f"Your IP address is: {client_ip}"

    @app.route('/debug')
    def debug_view():
        """Show debugging information (only available in debug mode)"""
        if not app.debug and not app.config.get('TESTING', False):
            return redirect(url_for('index'))
            
        debug_info = {
            "Flask Version": app.config.get('FLASK_VERSION', 'Unknown'),
            "Debug Mode": app.debug,
            "Database Path": app.config['DATABASE_PATH'],
            "Database Exists": os.path.exists(app.config['DATABASE_PATH']),
            "Routes": sorted([f"{rule.endpoint}: {rule}" for rule in app.url_map.iter_rules()]),
            "Config": {k: v for k, v in app.config.items() if not k.startswith('_') and k != 'SECRET_KEY'}
        }
        
        # Check if we can access the database
        db_status = "Unknown"
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM sqlite_master")
                count = cursor.fetchone()[0]
                db_status = f"Connected, {count} tables found"
                
                # Additional database diagnostics
                cursor.execute("PRAGMA integrity_check")
                integrity = cursor.fetchone()[0]
                db_status += f", Integrity: {integrity}"
        except Exception as e:
            db_status = f"Error: {str(e)}"
        
        debug_info["Database Status"] = db_status
        
        # Add registered event log count
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count(*) FROM event_logs")
                count = cursor.fetchone()[0]
                debug_info["Event Logs"] = count
        except Exception as e:
            debug_info["Event Logs"] = f"Error: {str(e)}"
        
        return render_template('debug.html', debug_info=debug_info)

    # 6. Error handlers
    @app.errorhandler(404)
    def page_not_found(e):
        """Handle 404 errors"""
        return render_template('error.html', 
                              error="Page not found. Please check the URL and try again."), 404

    @app.errorhandler(500)
    def internal_server_error(e):
        """Handle 500 errors"""
        app.logger.error(f"Internal Server Error: {str(e)}", exc_info=True)
        return render_template('error.html', 
                              error="Internal server error. Check the logs for details."), 500

    @app.errorhandler(Exception)
    def handle_exception(e):
        """Handle all other exceptions"""
        app.logger.error(f"Unhandled Exception: {str(e)}", exc_info=True)
        return render_template('error.html', 
                              error="An unexpected error occurred. Check the logs for details."), 500

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        """Handle CSRF errors"""
        app.logger.error(f"CSRF Error: {str(e)}")
        return render_template('error.html',
                              error="Security error. Please try again."), 400

    # Add routes for event logs
    @app.route('/event-logs')
    @login_required
    def event_logs():
        """View event logs"""
        logs = []
        action_filter = request.args.get('action', '')
        action_types = []
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Check if event_logs table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_logs'")
                if not cursor.fetchone():
                    flash("Event logs table doesn't exist yet. No logs available.", "warning")
                    return render_template('event_logs.html', logs=[], action_filter='', action_types=[])
                
                # Get available action types for filtering
                try:
                    cursor.execute("SELECT DISTINCT action_type FROM event_logs ORDER BY action_type")
                    action_types = [row['action_type'] for row in cursor.fetchall()]
                except Exception:
                    # If we can't get action types, continue with empty list
                    pass
                
                # Fetch logs with filtering if provided
                if action_filter:
                    cursor.execute("""
                        SELECT id, username, action_type, entity_type, item_id, details, timestamp
                        FROM event_logs
                        WHERE action_type = ?
                        ORDER BY timestamp DESC
                        LIMIT 200
                    """, (action_filter,))
                else:
                    cursor.execute("""
                        SELECT id, username, action_type, entity_type, item_id, details, timestamp
                        FROM event_logs
                        ORDER BY timestamp DESC
                        LIMIT 200
                    """)
                    
                logs = cursor.fetchall()
                
                # Debug output for the app logs
                app.logger.info(f"Retrieved {len(logs)} event logs" + 
                              (f" with filter '{action_filter}'" if action_filter else ""))
                
        except Exception as e:
            app.logger.error(f"Error fetching event logs: {str(e)}", exc_info=True)
            flash("Could not load event logs: " + str(e), "error")

        return render_template('event_logs.html', logs=logs, action_filter=action_filter, action_types=action_types)

    @app.route('/test-event-log')
    @login_required
    def test_event_log():
        """Test route to verify event logging system"""
        try:
            # Only allow in debug mode
            if not app.debug:
                flash("This feature is only available in debug mode", "warning")
                return redirect(url_for('dashboard'))
                
            # Create a test log entry
            log_event(
                current_user.id,
                current_user.username,
                'test',
                'system',
                None,
                f"Test log entry created at {time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            
            flash("Test event log created successfully. Check the event logs page.", "success")
            return redirect(url_for('event_logs', action='test'))
                
        except Exception as e:
            app.logger.error(f"Error in test event log: {str(e)}", exc_info=True)
            flash(f"Error creating test log: {str(e)}", "error")
            return redirect(url_for('event_logs'))

    @app.route('/reports', methods=['GET'])
    @login_required
    def generate_report():
        """Generate inventory and transfer reports"""
        report_type = request.args.get('type', 'inventory')  # Default to inventory report
        format_type = request.args.get('format', 'html')  # Default to HTML display
        from_date = request.args.get('from_date', '')
        to_date = request.args.get('to_date', '')

        # Initialize report data
        inventory_data = []
        transfer_data = []
        damaged_data = []
        opened_data = []
        
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                
                # Get inventory report data
                if report_type == 'inventory' or report_type == 'all':
                    cursor.execute("""
                        SELECT i.id, i.name, i.quantity, i.type, i.timestamp,
                               u.location_name
                        FROM inventory i
                        JOIN users u ON i.location_id = u.id
                        WHERE i.location_id = ?
                        ORDER BY i.type, i.name
                    """, (current_user.id,))
                    inventory_data = cursor.fetchall()
                
                # Get transfer report data with date filtering if provided
                if report_type == 'transfers' or report_type == 'all':
                    params = [current_user.id, current_user.id]
                    date_filter = ""
                    
                    if from_date and to_date:
                        date_filter = " AND t.timestamp BETWEEN ? AND ? "
                        params.extend([from_date, to_date])
                    elif from_date:
                        date_filter = " AND t.timestamp >= ? "
                        params.append(from_date)
                    elif to_date:
                        date_filter = " AND t.timestamp <= ? "
                        params.append(to_date)

                    cursor.execute(f"""
                        SELECT t.id, t.timestamp, t.quantity, t.transfer_tag,
                               i.name as item_name, i.type as item_type,
                               sent.location_name as from_location,
                               recv.location_name as to_location,
                               CASE 
                                   WHEN t.from_location_id = ? THEN 'Outgoing' 
                                   ELSE 'Incoming'
                               END as direction
                        FROM transfers t
                        JOIN inventory i ON t.item_id = i.id
                        JOIN users sent ON t.from_location_id = sent.id
                        JOIN users recv ON t.to_location_id = recv.id
                        WHERE (t.from_location_id = ? OR t.to_location_id = ?)
                        {date_filter}
                        ORDER BY t.timestamp DESC
                    """, params)
                    transfer_data = cursor.fetchall()
                
                # Get damaged items report data
                if report_type == 'damaged':
                    cursor.execute(
                        "SELECT * FROM damaged_items WHERE user_id = ? ORDER BY id DESC",
                        (current_user.id,)
                    )
                    damaged_data = cursor.fetchall()
                
                # Get opened items report data
                if report_type == 'opened':
                    cursor.execute(
                        "SELECT * FROM opened_items WHERE user_id = ? ORDER BY id DESC",
                        (current_user.id,)
                    )
                    opened_data = cursor.fetchall()
                
                # Get summary statistics
                cursor.execute("""
                    SELECT COUNT(*) as item_count, SUM(quantity) as total_quantity
                    FROM inventory
                    WHERE location_id = ?
                """, (current_user.id,))
                inventory_summary = cursor.fetchone()
                
                cursor.execute("""
                    SELECT 
                        (SELECT COUNT(*) FROM transfers WHERE from_location_id = ?) as outgoing,
                        (SELECT COUNT(*) FROM transfers WHERE to_location_id = ?) as incoming
                """, (current_user.id, current_user.id))
                transfer_summary = cursor.fetchone()
                
        except Exception as e:
            app.logger.error(f"Error generating report: {str(e)}")
            flash("Could not generate report data", "error")
            return redirect(url_for('dashboard'))
        
        # Handle different output formats
        if format_type == 'csv':
            # Generate CSV for download
            import csv
            from io import StringIO
            from flask import Response
            
            output = StringIO()
            csv_writer = csv.writer(output)
            
            if report_type == 'inventory' or report_type == 'all':
                csv_writer.writerow(['ID', 'Name', 'Type', 'Quantity', 'Location', 'Last Updated'])
                for item in inventory_data:
                    csv_writer.writerow([
                        item['id'], item['name'], item['type'], 
                        item['quantity'], item['location_name'], item['timestamp']
                    ])
                
            if report_type == 'transfers' or report_type == 'all':
                csv_writer.writerow(['ID', 'Date', 'Item', 'Type', 'Quantity', 'From', 'To', 'Direction', 'Reference'])
                for transfer in transfer_data:
                    csv_writer.writerow([
                        transfer['id'], transfer['timestamp'], transfer['item_name'],
                        transfer['item_type'], transfer['quantity'], 
                        transfer['from_location'], transfer['to_location'],
                        transfer['direction'], transfer['transfer_tag']
                    ])
            
            if report_type == 'damaged':
                csv_writer.writerow(['ID', 'Name', 'Quantity', 'Location'])
                for item in damaged_data:
                    csv_writer.writerow([item['id'], item['name'], item['quantity'], item['location']])
            
            if report_type == 'opened':
                csv_writer.writerow(['ID', 'Name', 'Quantity', 'Location'])
                for item in opened_data:
                    csv_writer.writerow([item['id'], item['name'], item['quantity'], item['location']])
            
            output.seek(0)
            filename = f"{report_type}_report_{time.strftime('%Y%m%d_%H%M%S')}.csv"
            
            # Log the report generation
            log_event(
                current_user.id,
                current_user.username,
                'export',
                f'{report_type}-report',
                None,
                f"Exported {report_type} report in CSV format"
            )
            
            return Response(
                output.getvalue(),
                mimetype="text/csv",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
        else:
            # Log the report generation
            log_event(
                current_user.id,
                current_user.username,
                'view',
                f'{report_type}-report',
                None,
                f"Viewed {report_type} report"
            )
            
            # Render HTML report
            return render_template(
                'reports.html',
                report_type=report_type,
                inventory_data=inventory_data,
                transfer_data=transfer_data,
                inventory_summary=inventory_summary,
                transfer_summary=transfer_summary,
                from_date=from_date,
                to_date=to_date,
                damaged_data=damaged_data,
                opened_data=opened_data
            )

    @app.route('/damaged', methods=['GET', 'POST'])
    @login_required
    def damaged_items():
        """Registrer og vis ødelagte produkter"""
        items = []
        if request.method == 'POST':
            name = request.form.get('name')
            quantity = request.form.get('quantity', type=int)
            location = request.form.get('location') or current_user.location_name
            if name and quantity is not None and location:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO damaged_items (name, quantity, location, user_id) VALUES (?, ?, ?, ?)",
                        (name, quantity, location, current_user.id)
                    )
                    conn.commit()
                flash('Ødelagt produkt registreret', 'success')
            else:
                flash('Alle felter skal udfyldes', 'error')
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM damaged_items WHERE user_id = ? ORDER BY id DESC",
                    (current_user.id,)
                )
                items = cursor.fetchall()
        except Exception as e:
            app.logger.error(f"Error fetching damaged items: {e}")
            flash('Kunne ikke hente ødelagte produkter', 'error')
        return render_template('damaged.html', items=items)

    @app.route('/opened', methods=['GET', 'POST'])
    @login_required
    def opened_items():
        """Registrer og vis anbrudte produkter"""
        items = []
        if request.method == 'POST':
            name = request.form.get('name')
            quantity = request.form.get('quantity', type=int)
            location = request.form.get('location') or current_user.location_name
            if name and quantity is not None and location:
                with get_db() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        "INSERT INTO opened_items (name, quantity, location, user_id) VALUES (?, ?, ?, ?)",
                        (name, quantity, location, current_user.id)
                    )
                    conn.commit()
                flash('Anbrud registreret', 'success')
            else:
                flash('Alle felter skal udfyldes', 'error')
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM opened_items WHERE user_id = ? ORDER BY id DESC",
                    (current_user.id,)
                )
                items = cursor.fetchall()
        except Exception as e:
            app.logger.error(f"Error fetching opened items: {e}")
            flash('Kunne ikke hente anbrud', 'error')
        return render_template('opened.html', items=items)

    @app.route('/ping')
    def ping():
        return "pong"

    @app.route('/damaged/csv')
    @login_required
    def damaged_csv():
        """Eksporter ødelagte produkter som CSV med dansk alfabet og /t foran dato"""
        import csv
        from io import StringIO
        from flask import Response

        items = []
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM damaged_items WHERE user_id = ? ORDER BY id DESC",
                    (current_user.id,)
                )
                items = cursor.fetchall()
        except Exception as e:
            app.logger.error(f"Error fetching damaged items for CSV: {e}")

        output = StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n')
        # Dansk header
        writer.writerow(['Navn', 'Antal', 'Lokation', 'Dato'])
        for item in items:
            # Dato med /t foran og dansk alfabet (utf-8)
            dato = f"/t{item['timestamp']}"
            writer.writerow([
                item['name'],
                item['quantity'],
                item['location'],
                dato
            ])
        output.seek(0)
        return Response(
            output.getvalue().encode('utf-8'),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=odelagte_produkter.csv"}
        )

    @app.route('/opened/csv')
    @login_required
    def opened_csv():
        """Eksporter anbrud som CSV med dansk alfabet og /t foran dato"""
        import csv
        from io import StringIO
        from flask import Response

        items = []
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM opened_items WHERE user_id = ? ORDER BY id DESC",
                    (current_user.id,)
                )
                items = cursor.fetchall()
        except Exception as e:
            app.logger.error(f"Error fetching opened items for CSV: {e}")

        output = StringIO()
        writer = csv.writer(output, delimiter=';', lineterminator='\n')
        # Dansk header
        writer.writerow(['Navn', 'Antal', 'Lokation', 'Dato'])
        for item in items:
            # Dato med /t foran og dansk alfabet (utf-8)
            dato = f"/t{item['timestamp']}"
            writer.writerow([
                item['name'],
                item['quantity'],
                item['location'],
                dato
            ])
        output.seek(0)
        return Response(
            output.getvalue().encode('utf-8'),
            mimetype="text/csv; charset=utf-8",
            headers={"Content-Disposition": "attachment; filename=anbrud.csv"}
        )