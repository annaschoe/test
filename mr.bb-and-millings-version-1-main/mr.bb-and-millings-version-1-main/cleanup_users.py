"""
Utility script to remove all users except for the admin (ID 1)
"""
import sqlite3
import os
import sys
import logging
from contextlib import contextmanager

# Add proper path for importing from the app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the configuration
try:
    from flask_app.config import Config
    db_path = Config.DATABASE_PATH
except ImportError:
    print("Error: Could not import Config. Make sure you're running this script from the project root.")
    # Fallback to common path if config import fails
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, 'flask_app', 'data', 'app.db')
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

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

def list_users():
    """List all users in the system"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, username, location_name FROM users ORDER BY id")
            users = cursor.fetchall()
            
            print("\n===== CURRENT USERS =====")
            for user in users:
                print(f"ID: {user['id']}, Username: {user['username']}, Location: {user['location_name']}")
            
            return users
    except Exception as e:
        logging.error(f"Error listing users: {e}")
        return []

def remove_users_except_admin():
    """Remove all users except for ID 1 (admin)"""
    try:
        # First, list all users
        users = list_users()
        
        # Now remove all except admin
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Temporarily disable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = OFF")
            
            # First, get all user IDs to remove
            cursor.execute("SELECT id FROM users WHERE id != 1")
            user_ids_to_remove = [row['id'] for row in cursor.fetchall()]
            
            if not user_ids_to_remove:
                print("\nNo additional users to remove.")
                return
            
            print(f"\nPreparing to remove {len(user_ids_to_remove)} users...")
            
            # For each user, remove related inventory and transfers
            for user_id in user_ids_to_remove:
                # First handle transfers where this user is either sender or receiver
                cursor.execute("""
                    DELETE FROM transfers 
                    WHERE from_location_id = ? OR to_location_id = ?
                """, (user_id, user_id))
                transfer_count = cursor.rowcount
                
                # Then remove inventory items
                cursor.execute("DELETE FROM inventory WHERE location_id = ?", (user_id,))
                inventory_count = cursor.rowcount
                
                print(f"User ID {user_id}: Removed {transfer_count} transfers and {inventory_count} inventory items")
            
            # Finally remove the users
            cursor.execute("DELETE FROM users WHERE id != 1")
            user_count = cursor.rowcount
            
            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON")
            
            # Commit changes
            conn.commit()
            
            print(f"\nSuccessfully removed {user_count} users. Only admin user (ID 1) remains.")
            
            # Verify by listing remaining users
            print("\nRemaining users:")
            list_users()
            
    except Exception as e:
        logging.error(f"Error removing users: {e}")
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print(f"Using database at: {db_path}")
    
    confirmation = input("\nThis script will remove ALL users except for ID 1 (admin).\nThis action cannot be undone and will delete all inventory and transfers for those users.\nType 'yes' to continue: ")
    
    if confirmation.lower() == 'yes':
        remove_users_except_admin()
        print("\nCleanup completed. The system now has only the admin user (ID 1).")
    else:
        print("Operation cancelled.")
