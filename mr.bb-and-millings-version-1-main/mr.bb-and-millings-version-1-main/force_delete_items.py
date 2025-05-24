"""
Script to force delete specific items from the inventory database,
including any transfer records that reference them.
"""
import sqlite3
import os
import sys
import logging

# Configure logging to console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Get the database path
try:
    from config import Config
    db_path = Config.DATABASE_PATH
except ImportError:
    # Fallback to default path
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_path = os.path.join(base_dir, "flask_app", "data", "app.db")
    
    # Check if database exists at common locations
    if not os.path.exists(db_path):
        alt_paths = [
            os.path.join(base_dir, "data", "app.db"),
            os.path.join(base_dir, "instance", "app.db"),
            os.path.join(base_dir, "flask_app", "app.db")
        ]
        for path in alt_paths:
            if os.path.exists(path):
                db_path = path
                break
        else:
            logging.error("Database not found. Please provide the database path manually.")
            logging.info("Possible locations could be:")
            logging.info("- data/app.db")
            logging.info("- instance/app.db")
            logging.info("- flask_app/app.db")
            sys.exit(1)

def execute_force_delete():
    conn = None
    try:
        logging.info(f"Connecting to database at: {db_path}")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Disable foreign key constraints temporarily
        cursor.execute("PRAGMA foreign_keys = OFF")
        
        # 1. Find items containing "Cracktingz" or "pussyclats"
        specific_items = ["Cracktingz", "pussyclats"]
        all_item_ids = []
        
        for item_name in specific_items:
            cursor.execute(
                "SELECT id, name FROM inventory WHERE LOWER(name) LIKE LOWER(?)", 
                (f"%{item_name}%",)
            )
            items = cursor.fetchall()
            
            if items:
                logging.info(f"Found {len(items)} items matching '{item_name}':")
                for item in items:
                    logging.info(f"  ID: {item['id']}, Name: {item['name']}")
                    all_item_ids.append(item['id'])
            else:
                logging.info(f"No items found matching '{item_name}'")
        
        if not all_item_ids:
            logging.info("No matching items found to delete.")
            return
        
        # 2. Find and delete transfer records for these items
        placeholders = ','.join(['?'] * len(all_item_ids))
        cursor.execute(
            f"SELECT COUNT(*) as count FROM transfers WHERE item_id IN ({placeholders})",
            all_item_ids
        )
        transfer_count = cursor.fetchone()['count']
        
        if transfer_count > 0:
            logging.info(f"Deleting {transfer_count} transfer records...")
            cursor.execute(
                f"DELETE FROM transfers WHERE item_id IN ({placeholders})",
                all_item_ids
            )
            logging.info(f"Successfully deleted {transfer_count} transfer records.")
        
        # 3. Delete the inventory items
        for item_id in all_item_ids:
            cursor.execute("DELETE FROM inventory WHERE id = ?", (item_id,))
            logging.info(f"Deleted inventory item with ID {item_id}")
        
        # Commit changes
        conn.commit()
        logging.info("All specified items and their transfer records have been successfully deleted.")
        
        # Re-enable foreign key constraints
        cursor.execute("PRAGMA foreign_keys = ON")
        
    except sqlite3.Error as e:
        logging.error(f"Database error: {e}")
        return False
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        return False
    finally:
        if conn:
            conn.close()
    
    return True

if __name__ == "__main__":
    print("=" * 70)
    print("EMERGENCY ITEM DELETION TOOL")
    print("=" * 70)
    print(f"This tool will DELETE items containing 'Cracktingz' or 'pussyclats'")
    print(f"Database: {db_path}")
    print("\nWARNING: This will:")
    print("  1. Temporarily disable database foreign key constraints")
    print("  2. Delete ALL transfer records referencing these items")
    print("  3. Delete the items themselves")
    print("\nThis action CANNOT be undone!")
    print("=" * 70)
    
    confirm = input("\nType 'DELETE CONFIRMED' to proceed: ")
    if confirm == "DELETE CONFIRMED":
        print("\nProceeding with deletion...")
        if execute_force_delete():
            print("\nDeletion completed successfully!")
        else:
            print("\nDeletion failed. Check the error messages above.")
    else:
        print("\nDeletion cancelled.")
