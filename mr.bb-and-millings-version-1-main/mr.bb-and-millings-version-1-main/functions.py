"""
Utility functions for the Flask application
"""
import logging
from functools import wraps
from flask import request, flash
from datetime import datetime

# This will be set by importing app.py
app = None

def format_datetime(value, format="%Y-%m-%d %H:%M:%S"):
    """
    Format a datetime object according to the specified format.
    If a string is passed, it attempts to parse it as a datetime first.
    
    Args:
        value: The datetime object or string to format
        format: The format string to use (default: "%Y-%m-%d %H:%M:%S")
        
    Returns:
        The formatted datetime string
    """
    if not value:
        return ""
        
    if isinstance(value, str):
        try:
            # Try to parse the string as a datetime with common formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%m/%d/%Y"]:
                try:
                    value = datetime.strptime(value, fmt)
                    break
                except ValueError:
                    continue
        except Exception as e:
            app.logger.warning(f"Error parsing datetime string: {str(e)}")
            return value
    
    if not isinstance(value, datetime):
        # If it's not a datetime by now, return as is
        return value
        
    try:
        return value.strftime(format)
    except Exception as e:
        app.logger.warning(f"Error formatting datetime: {str(e)}")
        return str(value)

def inject_now():
    """
    Inject current datetime into templates
    """
    return {'now': datetime.now()}
        
def validate_form_data(required_fields=None, validators=None):
    """
    Decorator that validates form data based on specified requirements.
    
    Args:
        required_fields: List of field names that must be present and non-empty
        validators: Dict mapping field names to validation functions
    """
    required_fields = required_fields or []
    validators = validators or {}
    
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            errors = []
            
            # Check required fields
            for field in required_fields:
                if not request.form.get(field, '').strip():
                    errors.append(f"{field} cannot be empty")
            
            # Apply field-specific validators
            for field, validator in validators.items():
                if field in request.form:
                    try:
                        if not validator(request.form[field]):
                            errors.append(f"Invalid value for {field}")
                    except Exception as e:
                        errors.append(f"Error validating {field}: {str(e)}")
            
            if errors:
                for error in errors:
                    flash(f"❌ {error}", "error")
                return None
                
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def inject_now():
    """Add the current datetime to all template contexts for the footer's year"""
    return {'now': datetime.now()}
