"""Database utility functions to separate data access from application logic."""

import sqlite3
from contextlib import contextmanager
import logging
import time
import os
import stat
from werkzeug.security import generate_password_hash
from typing import Any, Dict, List, Optional, Tuple

# Add a global app variable that can be set from outside
app = None

def get_app():
    """Get the Flask app instance, with fallback mechanisms."""
    global app
    if app is not None:
        return app
    
    try:
        # Try absolute import first (more reliable)
        import app as flask_app_module
        return flask_app_module.app
    except (ImportError, AttributeError):
        try:
            from . import app as flask_app
            return flask_app
        except (ImportError, AttributeError):
            try:
                from app import app as flask_app
                return flask_app
            except ImportError:
                logging.error("Could not import Flask app instance!")
                raise RuntimeError("Flask app instance not available")

@contextmanager
def get_db():
    """Database connection context manager with connection pooling and retry logic."""
    # Get the app instance - either from module variable or by importing
    flask_app = get_app()
    conn = None
    try:
        if not hasattr(flask_app, 'db_pool'):
            flask_app.db_pool = []
            flask_app.last_pool_check = time.time()
        
        _recycle_db_pool_if_needed(flask_app)
        
        conn = _get_connection_from_pool(flask_app)
        if conn is not None:
            yield conn
            return
        
        conn = _create_new_db_connection(flask_app)
        yield conn
        
        flask_app.db_pool.append(conn)
    except Exception as e:
        logging.error(f"Database connection error: {e}", exc_info=True)
        raise
    finally:
        if conn and conn not in getattr(flask_app, 'db_pool', []):
            try:
                conn.close()
            except Exception:
                pass

def _recycle_db_pool_if_needed(app):
    """Check if connection pool needs recycling."""
    now = time.time()
    if hasattr(app, 'last_pool_check') and now - app.last_pool_check > 300:
        try:
            old_pool = app.db_pool
            app.db_pool = []
            for old_conn in old_pool:
                try:
                    old_conn.close()
                except Exception:
                    pass
            logging.info("Database connection pool recycled")
        except Exception as e:
            logging.error(f"Error recycling connection pool: {e}")
        app.last_pool_check = now

def _get_connection_from_pool(app):
    """Get valid connection from pool."""
    while app.db_pool and len(app.db_pool) > 0:
        try:
            conn = app.db_pool.pop()
            if conn:
                conn.execute("SELECT 1")
                return conn
        except sqlite3.Error:
            try:
                if conn:
                    conn.close()
            except Exception:
                pass
    return None

def _create_new_db_connection(app):
    """Create new SQLite connection with optimized settings."""
    # First ensure the directory exists with proper permissions
    db_dir = os.path.dirname(app.config['DATABASE_PATH'])
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            # On Unix systems, set directory permissions to be restrictive
            if os.name == 'posix':
                os.chmod(db_dir, stat.S_IRWXU)  # 700 permissions (rwx for owner only)
        except Exception as e:
            logging.error(f"Failed to create database directory: {e}")
            raise
            
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = sqlite3.connect(
                app.config['DATABASE_PATH'],
                timeout=app.config['SQLITE_TIMEOUT']
            )
            conn.row_factory = sqlite3.Row
            
            # Apply optimized SQLite settings
            conn.execute('PRAGMA busy_timeout = 30000')
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA foreign_keys = ON')
            conn.execute('PRAGMA cache_size = -2000')  # 2MB cache
            
            # Check and fix permissions after creating the connection
            set_db_permissions(app)
            
            return conn
        except sqlite3.Error as e:
            if attempt == max_retries - 1:
                logging.error(f"Failed to connect after {max_retries} attempts: {e}")
                raise
            time.sleep(1)
    
    raise RuntimeError("Failed to create database connection")

def set_db_permissions(app):
    """Set correct permissions on the database file."""
    try:
        if os.path.exists(app.config['DATABASE_PATH']):
            # Make the database readable/writable by owner only
            # For Windows this doesn't have the same effect, but won't cause errors
            os.chmod(app.config['DATABASE_PATH'], app.config['DATABASE_PERMISSIONS'])
            logging.info(f"Set database file permissions to {oct(app.config['DATABASE_PERMISSIONS'])}")
    except Exception as e:
        logging.error(f"Could not set database file permissions: {e}")

def init_db(app):
    """Initialize database schema and create default admin user if needed."""
    try:
        os.makedirs(os.path.dirname(app.config['DATABASE_PATH']), exist_ok=True)

        # Remove the database file if it exists to avoid FK constraint errors
        db_path = app.config['DATABASE_PATH']
        if os.path.exists(db_path):
            os.remove(db_path)

        with get_db() as conn:
            cursor = conn.cursor()
            # Drop all relevant tables to force full recreation
            cursor.executescript('''
                DROP TABLE IF EXISTS transfers;
                DROP TABLE IF EXISTS inventory;
                DROP TABLE IF EXISTS users;
                DROP TABLE IF EXISTS damaged_items;
                DROP TABLE IF EXISTS opened_items;
                DROP TABLE IF EXISTS event_logs;
            ''')
            # Create all tables from scratch
            cursor.executescript('''
                CREATE TABLE users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT UNIQUE NOT NULL,
                    password TEXT NOT NULL,
                    location_name TEXT NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE inventory (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity >= 0),
                    type TEXT NOT NULL,
                    location_id INTEGER NOT NULL,
                    transfer_tag TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (location_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE transfers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    from_location_id INTEGER NOT NULL,
                    to_location_id INTEGER NOT NULL,
                    item_id INTEGER NOT NULL,
                    quantity INTEGER NOT NULL CHECK (quantity > 0),
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    transfer_tag TEXT,
                    FOREIGN KEY (from_location_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (to_location_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (item_id) REFERENCES inventory(id) ON DELETE CASCADE
                );

                CREATE TABLE damaged_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    user_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE opened_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    user_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE event_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    item_id INTEGER,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                );

                CREATE INDEX idx_inventory_location ON inventory(location_id);
                CREATE INDEX idx_transfers_from ON transfers(from_location_id);
                CREATE INDEX idx_transfers_to ON transfers(to_location_id);
                CREATE INDEX IF NOT EXISTS idx_event_logs_user ON event_logs(user_id);
            ''')

            # Create admin user with fixed hash method
            default_admin = app.config['DEFAULT_ADMIN']
            hashed_password = generate_password_hash(default_admin['password'], method='pbkdf2:sha256')
            cursor.execute(
                "INSERT INTO users (username, password, location_name) VALUES (?, ?, ?)",
                (
                    default_admin['username'],
                    hashed_password,
                    default_admin['location']
                )
            )
            conn.commit()
            logging.info(f"First user created - Username: {default_admin['username']}")
        
        # Set proper permissions after database initialization
        set_db_permissions(app)
            
    except Exception as e:
        logging.error(f"Error initializing database: {str(e)}")
        raise

def check_db_initialized(app):
    """Check if the database is properly initialized by verifying essential tables."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name IN ('users', 'inventory', 'transfers')")
            tables = cursor.fetchall()
            return len(tables) == 3
    except Exception as e:
        logging.error(f"Error checking database initialization: {e}")
        return False

def migrate_db(app):
    """Perform database migrations as needed"""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Ensure proper indexes exist for performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_location 
                ON inventory(location_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_name 
                ON inventory(name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_type 
                ON inventory(type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_loc_name_type 
                ON inventory(location_id, name, type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_users_username 
                ON users(username)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_name 
                ON inventory(name)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_type 
                ON inventory(type)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_inventory_loc_name_type 
                ON inventory(location_id, name, type)
            """)
            
            # Add any new columns if needed
            has_timestamp_column = False
            try:
                cursor.execute("SELECT timestamp FROM inventory LIMIT 1")
                has_timestamp_column = True
            except sqlite3.OperationalError:
                # Column doesn't exist - add it first without a default value
                logging.info("Adding timestamp column to inventory table")
                cursor.execute("ALTER TABLE inventory ADD COLUMN timestamp DATETIME")
                
                # Then update all existing rows with the current timestamp
                cursor.execute("UPDATE inventory SET timestamp = datetime('now')")
                
                # Create a trigger to set timestamp for new rows
                cursor.execute("""
                CREATE TRIGGER IF NOT EXISTS set_inventory_timestamp
                AFTER INSERT ON inventory
                BEGIN
                    UPDATE inventory SET timestamp = datetime('now') WHERE id = NEW.id AND timestamp IS NULL;
                END
                """)
                
                logging.info("Added timestamp column and trigger to inventory table")
            
            # Create event_logs table if it doesn't exist
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS event_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    username TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    item_id INTEGER,
                    details TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            """)
            logging.info("Ensured event_logs table exists")
            
            # Create index on event_logs
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_event_logs_user
                ON event_logs(user_id)
            """)
            
            conn.commit()
    except Exception as e:
        logging.error(f"Database migration error: {e}")

# Add utility function to log events
def log_event(user_id, username, action_type, entity_type, item_id=None, details=None):
    """
    Log a user action in the event_logs table
    
    Args:
        user_id: ID of the user performing the action
        username: Username of the user performing the action
        action_type: Type of action (create, update, delete, etc.)
        entity_type: Type of entity being acted on (inventory, transfer, user, etc.)
        item_id: ID of the item being acted on (optional)
        details: Additional details about the action (optional)
    """
    try:
        # Debug logging to help diagnose issues
        logging.debug(f"Logging event: {action_type} {entity_type} by {username} (ID: {user_id})")
        
        with get_db() as conn:
            cursor = conn.cursor()
            
            # Verify event_logs table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='event_logs'")
            if not cursor.fetchone():
                logging.error("event_logs table doesn't exist, attempting to create it")
                # Try to create the table if it doesn't exist
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS event_logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        username TEXT NOT NULL,
                        action_type TEXT NOT NULL, 
                        entity_type TEXT NOT NULL,
                        item_id INTEGER,
                        details TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                conn.commit()
            
            # Insert the event log with explicit commit
            cursor.execute(
                "INSERT INTO event_logs (user_id, username, action_type, entity_type, item_id, details) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, username, action_type, entity_type, item_id, details)
            )
            conn.commit()
            
            # Verify the log was created
            cursor.execute("SELECT id FROM event_logs WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            result = cursor.fetchone()
            if result:
                logging.debug(f"Successfully created event log with ID {result['id']}")
            else:
                logging.error("Failed to verify event log creation")
                
    except Exception as e:
        logging.error(f"Error logging event: {str(e)}", exc_info=True)
        # Re-raise the exception if in debug mode
        flask_app = get_app()
        if flask_app.debug:
            raise

def ensure_extra_tables():
    """Ensure damaged_items and opened_items tables always exist."""
    try:
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS damaged_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    user_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS opened_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    location TEXT NOT NULL,
                    user_id INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()
    except Exception as e:
        logging.error(f"Error ensuring extra tables: {e}")

# Sørg for at denne funktion bliver kaldt når app'en starter (fx i __init__.py)
from app import app
from database import init_db
init_db(app)
