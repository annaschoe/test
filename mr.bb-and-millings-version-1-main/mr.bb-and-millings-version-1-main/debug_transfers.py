"""
Utility script to debug transfers between users
"""
import sqlite3
import sys
import os
import logging
from contextlib import contextmanager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Try to get database path from config
try:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from flask_app.config import Config
    db_path = Config.DATABASE_PATH
except ImportError:
    # Default database path if config not available
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'flask_app', 'data', 'app.db')

@contextmanager
def get_db_connection():
    """Get a database connection"""
    conn = None
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()

def list_all_users():
    """List all users in the system"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, location_name FROM users")
            users = cursor.fetchall()
            
            print("\n===== USERS IN THE SYSTEM =====")
            for user in users:
                print(f"ID: {user['id']}, Username: {user['username']}, Location: {user['location_name']}")
    except Exception as e:
        logging.error(f"Error listing users: {e}")

def check_inventory_for_user(user_id):
    """Check inventory items for a specific user"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Get user info
            cursor.execute("SELECT username, location_name FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            
            if not user:
                print(f"No user found with ID {user_id}")
                return
                
            # Get inventory items
            cursor.execute("""
                SELECT id, name, quantity, type, transfer_tag
                FROM inventory
                WHERE location_id = ?
            """, (user_id,))
            items = cursor.fetchall()
            
            print(f"\n===== INVENTORY FOR {user['username']} ({user['location_name']}) =====")
            if items:
                for item in items:
                    transfer_info = f", Transfer: {item['transfer_tag']}" if item['transfer_tag'] else ""
                    print(f"ID: {item['id']}, Name: {item['name']}, Qty: {item['quantity']}, Type: {item['type']}{transfer_info}")
            else:
                print("No inventory items found")
    except Exception as e:
        logging.error(f"Error checking inventory: {e}")

def check_transfers():
    """Check all transfers in the system"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.id, t.from_location_id, u1.username as sender,
                       t.to_location_id, u2.username as receiver,
                       i.name as item_name, t.quantity, t.timestamp, t.transfer_tag
                FROM transfers t
                JOIN users u1 ON t.from_location_id = u1.id
                JOIN users u2 ON t.to_location_id = u2.id
                JOIN inventory i ON t.item_id = i.id
                ORDER BY t.timestamp DESC
            """)
            transfers = cursor.fetchall()
            
            print("\n===== TRANSFERS IN THE SYSTEM =====")
            if transfers:
                for t in transfers:
                    print(f"ID: {t['id']}, From: {t['sender']} -> To: {t['receiver']}, " 
                          f"Item: {t['item_name']}, Qty: {t['quantity']}, " 
                          f"Time: {t['timestamp']}, Tag: {t['transfer_tag']}")
            else:
                print("No transfers found")
    except Exception as e:
        logging.error(f"Error checking transfers: {e}")

def fix_missing_items():
    """Attempt to fix missing items by checking transfers without corresponding inventory"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Find transfers where the recipient doesn't have the item
            cursor.execute("""
                SELECT t.*, i.name, i.type
                FROM transfers t
                JOIN inventory i ON t.item_id = i.id
                WHERE NOT EXISTS (
                    SELECT 1 FROM inventory 
                    WHERE location_id = t.to_location_id 
                    AND name = i.name 
                    AND type = i.type
                )
            """)
            missing_items = cursor.fetchall()
            
            if not missing_items:
                print("\nNo missing items detected!")
                return
                
            print(f"\nFound {len(missing_items)} transfers with missing items in recipient inventory")
            
            # Fix each missing item
            for item in missing_items:
                print(f"Creating missing item from transfer ID {item['id']}: {item['name']} for user ID {item['to_location_id']}")
                
                # Create the missing item
                cursor.execute("""
                    INSERT INTO inventory 
                    (name, quantity, type, location_id, transfer_tag)
                    VALUES (?, ?, ?, ?, ?)
                """, (item['name'], item['quantity'], item['type'], item['to_location_id'], item['transfer_tag']))
            
            conn.commit()
            print("Fixed all missing items!")
            
    except Exception as e:
        logging.error(f"Error fixing missing items: {e}")

if __name__ == "__main__":
    print(f"Using database at: {db_path}")
    list_all_users()
    
    user_input = input("\nEnter user ID to check inventory (or press Enter to skip): ")
    if user_input.strip():
        try:
            user_id = int(user_input)
            check_inventory_for_user(user_id)
        except ValueError:
            print("Invalid user ID")
    
    check_transfers()
    
    fix_option = input("\nWould you like to attempt to fix missing items? (y/n): ")
    if fix_option.lower() == 'y':
        fix_missing_items()
