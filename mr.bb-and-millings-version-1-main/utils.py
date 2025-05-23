"""Utility functions for the application."""

from flask import request, flash
from functools import wraps
from typing import Callable, Dict, Any, Optional

class DummyLimiter:
    def limit(self, *args, **kwargs):
        def decorator(f):
            return f
        return decorator

def validate_form_data(required_fields=None, validators=None):
    """
    Decorator that validates form data based on specified requirements.
    
    Args:
        required_fields: List of field names that must be present and non-empty
        validators: Dict mapping field names to validation functions
    """
    # ...existing code...
