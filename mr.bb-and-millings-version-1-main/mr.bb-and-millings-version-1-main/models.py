"""
Database models for the application
"""

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import logging
from .database import get_db

class User(UserMixin):
    def __init__(self, id, username, location_name):
        self.id = id
        self.username = username
        self.location_name = location_name
        
    def get_id(self):
        return str(self.id)
        
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
            logging.error(f"Error loading user: {e}")
        return None
        
    @staticmethod
    def authenticate(username, password):
        """Authenticate a user by username and password"""
        try:
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
                user = cursor.fetchone()
                
                if user and check_password_hash(user['password'], password):
                    return User(user['id'], user['username'], user['location_name'])
        except Exception as e:
            logging.error(f"Authentication error: {e}")
        return None
