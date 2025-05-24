"""
Script to remove specific items from the inventory database
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
except ImportError:
    print("Error: Could not import Config. Make sure you're running this script from the project root.")
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
        conn = sqlite3.connect(Config.DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        yield conn
    finally:
        if conn:
            conn.close()

def remove_items(items_to_remove):
    """Remove specified items from the inventory"""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # First check if any items are referenced in transfers
            for item_name in items_to_remove:
                cursor.execute("""
                    SELECT t.* FROM transfers t
                    JOIN inventory i ON t.item_id = i.id
                    WHERE i.name LIKE ?
                """, (f"%{item_name}%",))
                
                transfers = cursor.fetchall()
                if transfers:
                    logging.warning(f"Item '{item_name}' has {len(transfers)} transfer records. These will be deleted first.")
                    
                    # Get the IDs of the inventory items to delete
                    cursor.execute("SELECT id FROM inventory WHERE name LIKE ?", (f"%{item_name}%",))
                    item_ids = [row['id'] for row in cursor.fetchall()]
                    
                    # Delete the transfers for these items
                    for item_id in item_ids:
                        cursor.execute("DELETE FROM transfers WHERE item_id = ?", (item_id,))
                        logging.info(f"Deleted transfer records for item ID {item_id}")
            
            # Now delete the inventory items
            for item_name in items_to_remove:
                cursor.execute("DELETE FROM inventory WHERE name LIKE ?", (f"%{item_name}%",))
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    logging.info(f"Deleted {deleted_count} items containing '{item_name}'")
                else:
                    logging.warning(f"No items found containing '{item_name}'")
            
            conn.commit()
            logging.info("Item deletion completed successfully")
            
    except sqlite3.Error as e:
        logging.error(f"SQLite error: {e}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")

if __name__ == "__main__":
    items_to_remove = ["Cracktingz", "pussyclats"]
    
    print(f"This script will remove all inventory items containing the following terms: {', '.join(items_to_remove)}")
    print("This action cannot be undone!")
    
    confirmation = input("Type 'yes' to continue or anything else to cancel: ")
    
    if confirmation.lower() == 'yes':
        remove_items(items_to_remove)
        print("Removal process completed. Check the logs for details.")
    else:
        print("Operation cancelled.")
