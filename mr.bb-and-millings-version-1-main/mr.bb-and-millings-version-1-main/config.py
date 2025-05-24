import os
import secrets
from datetime import timedelta

class Config:
    # Application paths
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, 'inventory.db')
    TEMP_DIR = os.path.join(BASE_DIR, 'temp')
    LOG_DIR = os.path.join(BASE_DIR, 'logs')

    # Security - generate a random secret key or use environment variable
    SECRET_KEY = os.environ.get('SECRET_KEY') or secrets.token_hex(16)
    
    # Security settings
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    SESSION_COOKIE_SECURE = os.environ.get('PRODUCTION', 'False') == 'True'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Database settings
    SQLITE_TIMEOUT = 30
    TEMP_FILE_RETENTION_HOURS = 1

    # Application settings
    ITEM_TYPES = ["Glass", "Plastic", "Metal"]

    # Password requirements
    PASSWORD_MIN_LENGTH = 8
    PASSWORD_REQUIRE_SPECIAL = True

    # Default admin user settings
    DEFAULT_ADMIN = {
        'username': 'admin',
        'password': 'admin_password',  # Consider using environment variable in production
        'location': 'default_location'
    }
    
    # Add missing configuration values
    DEBUG = os.environ.get('FLASK_DEBUG', 'False') == 'True'
    TESTING = False
    
    # Database configuration
    DATABASE_NAME = 'inventory.db'
    DATABASE_PATH = os.path.join(BASE_DIR, DATABASE_NAME)
    DATABASE_PERMISSIONS = 0o600  # Readable by owner and group, not others
    
    # Rate limiting
    RATELIMIT_DEFAULT = ["200 per day", "50 per hour"]
    RATELIMIT_STORAGE_URI = "memory://"
    
    # CSRF protection
    WTF_CSRF_TIME_LIMIT = 3600  # 1 hour
    
    # Logging configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO')
    LOG_FORMAT = '%(asctime)s [%(levelname)s] %(message)s'
    LOG_MAX_BYTES = 1024 * 1024  # 1MB
    LOG_BACKUP_COUNT = 5
