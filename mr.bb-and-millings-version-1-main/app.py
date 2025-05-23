import logging
try:
    from concurrent_log_handler import ConcurrentRotatingFileHandler as RotatingFileHandler
except ImportError:
    from logging.handlers import RotatingFileHandler
from flask import Flask, render_template, redirect, url_for
import os
import sys
from config import Config
from flask_wtf.csrf import CSRFProtect
from flask_login import LoginManager, UserMixin, current_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime
import traceback

# Initialize Flask app
app = Flask(__name__)
app.config.from_object(Config)
csrf = CSRFProtect(app)

# Fix imports - use absolute import instead of relative import to avoid errors
# Add the current directory to path for absolute imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import functions
import database
# Set app reference in modules
functions.app = app
database.app = app  # Add this line to ensure database module has app reference

# Import utility functions with explicit names for clarity
from functions import validate_form_data, inject_now, format_datetime
from database import get_db, set_db_permissions, init_db, check_db_initialized, migrate_db

# Initialize Login Manager
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Please log in to access this page"
login_manager.login_message_category = "info"

# Initialize Limiter with robust error handling
try:
    # Initialize limiter with a more robust approach that avoids typical errors
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    
    # First create limiter without attaching to app
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=["200 per day", "50 per hour"],
        storage_uri="memory://",
        strategy="fixed-window"
    )
    
    # Then initialize it with the app
    limiter.init_app(app)
    
except Exception as e:
    logging.error(f"Error initializing Flask-Limiter: {e}")
    class DummyLimiter:
        def limit(self, *args, **kwargs):
            def decorator(f):
                return f
            return decorator
    limiter = DummyLimiter()

# Define User class
class User(UserMixin):
    def __init__(self, id, username, location_name):
        self.id = id
        self.username = username
        self.location_name = location_name
        
    def get_id(self):
        return str(self.id)  # Ensure ID is returned as a string
    
    @staticmethod
    def get_by_id(user_id):
        """Load user by ID from database"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
                user = cursor.fetchone()
                if user:
                    return User(user['id'], user['username'], user['location_name'])
        except Exception as e:
            logging.error(f"Error loading user by ID: {e}")
        return None

# Register the loader callback
@login_manager.user_loader
def load_user(user_id):
    return User.get_by_id(user_id)

# Configure logging
LOG_DIR = os.path.join(app.root_path, 'logs')
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    handlers=[
        RotatingFileHandler(
            os.path.join(LOG_DIR, 'app.log'),
            maxBytes=1024 * 4,  # ~4KB per log file
            backupCount=5
        )
    ],
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# Register the context processor
app.context_processor(inject_now)

# Register template filters
app.jinja_env.filters['format_datetime'] = format_datetime

# Import and register routes AFTER app initialization to avoid circular imports
from routes import register_routes
register_routes(app)

# Modified main block with debug mode from environment variable
if __name__ == '__main__':
    try:
        # Create required directories with better error handling
        required_dirs = [
            os.path.dirname(app.config['DATABASE_PATH']),
            app.config.get('TEMP_DIR', os.path.join(app.root_path, 'temp')),
            LOG_DIR
        ]
        
        for directory in required_dirs:
            try:
                os.makedirs(directory, exist_ok=True)
            except Exception as e:
                logging.error(f"Error creating directory {directory}: {e}")
                
        try:
            # Explicitly pass app to these functions
            migrate_db(app)
        except Exception as e:
            logging.error(f"Migration error: {e}")
            
        try:
            # Explicitly pass app to these functions
            init_db(app)
        except Exception as e:
            logging.error(f"Database initialization error: {e}", exc_info=True)
            
        # Get debug mode from environment variable
        debug_mode = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
        if debug_mode:
            logging.info("Starting server in DEBUG mode")
        else:
            logging.info("Starting server in PRODUCTION mode")
              # Use 0.0.0.0 to listen on all interfaces
        app.run(
            host='0.0.0.0',        # Changed from 127.0.0.1 to allow external connections
            port=int(os.getenv('FLASK_PORT', '5000')),
            debug=debug_mode
        )
    except Exception as e:
        logging.critical(f"Critical error: {str(e)}", exc_info=True)
        raise

# Example of a debug route (commented out to avoid route conflicts)
# @app.route('/debug-dashboard')
# def debug_dashboard():
#     try:
#         # Debug version of the dashboard
#         return render_template(
#             'dashboard.html', 
#             current_user=current_user,
#             now=datetime.now(),
#             stats=stats,
#             recent_activity=recent_activity,
#             inventory_items=inventory_items
#         )
#     except Exception as e:
#         app.logger.error(f"Dashboard error: {str(e)}")
#         app.logger.error(traceback.format_exc())
#         return f"""
#         <h1>Dashboard Error</h1>
#         <p>There was an error rendering the dashboard:</p>
#         <pre>{str(e)}</pre>
#         <p>Please check the logs for more details.</p>
#         """