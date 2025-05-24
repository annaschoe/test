"""
Festival Logistics application package
"""

from flask import Flask, request
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect, generate_csrf
import os
import logging
from logging.handlers import RotatingFileHandler
import sys

# Create app outside of create_app for compatibility with existing code
app = Flask(__name__)

# Define create_app function for potential future use with application factories
def create_app(config_class=None):
    # If app was already initialized, return it
    global app
    
    # Load configuration
    if config_class:
        app.config.from_object(config_class)
    else:
        from .config import Config
        app.config.from_object(Config)
    
    # Set up CSRF protection
    csrf = CSRFProtect(app)
    
    # Set up login manager
    login_manager = LoginManager(app)
    login_manager.login_view = 'login'
    login_manager.login_message = 'Please log in to access this page'
    login_manager.login_message_category = 'info'
    
    # Configure logging
    LOG_DIR = os.path.join(app.root_path, 'logs')
    os.makedirs(LOG_DIR, exist_ok=True)
    
    logging.basicConfig(
        handlers=[
            RotatingFileHandler(
                os.path.join(LOG_DIR, 'app.log'),
                maxBytes=1024 * 1024,
                backupCount=5
            ),
            logging.StreamHandler()  # Log to console as well
        ],
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )
    
    # Set up modules
    from . import functions
    functions.app = app
    
    from . import database
    database.app = app

    # Ensure all tables are created (including damaged_items and opened_items)
    database.ensure_extra_tables()

    # Import views/routes
    from . import routes
    
    return app

@app.context_processor
def inject_request():
    return dict(request=request)

@app.context_processor
def inject_csrf_token():
    return dict(csrf_token=generate_csrf())

# For backwards compatibility
if 'app' in locals():
    # Make sure modules have app reference
    try:
        from . import functions
        functions.app = app
        
        from . import database
        database.app = app
    except ImportError:
        pass
