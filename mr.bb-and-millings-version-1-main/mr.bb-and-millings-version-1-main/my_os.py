"""
Custom OS module wrapper to ensure consistent behavior across platforms
"""
# Import the standard os module
import os as _os

# Re-export all attributes from the standard os module
from os import *

# Add any custom functions or modifications here
def makedirs(name, mode=0o777, exist_ok=False):
    """Wrapper for os.makedirs to add extra logging or handling if needed"""
    return _os.makedirs(name, mode=mode, exist_ok=exist_ok)

def path_exists(path):
    """Check if path exists with proper error handling"""
    try:
        return _os.path.exists(path)
    except Exception:
        return False

# Add aliases for commonly used functions
exists = _os.path.exists
join = _os.path.join
