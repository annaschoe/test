#!/usr/bin/env python
"""
Django's command-line utility for administrative tasks.
This is a redirector that points to the actual project in 'main version 2' folder.
"""
import os
import sys
import subprocess
import warnings

# Show a warning about the directory change
warnings.warn("\nWARNING: Running Django from the parent directory.\n"
              "Please change to the 'main version 2' directory instead.\n"
              "For now, redirecting to the correct location...\n")

# Change to the correct directory
PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main version 2")
os.chdir(PROJECT_DIR)

# Execute the manage.py in the correct directory
if __name__ == "__main__":
    # Add the project directory to Python path
    if PROJECT_DIR not in sys.path:
        sys.path.insert(0, PROJECT_DIR)
    
    # Get the same arguments that were passed to this script
    command = [sys.executable, "manage.py"] + sys.argv[1:]
    
    print(f"\n=== Redirecting to Django in: {PROJECT_DIR} ===\n")
    print(f"Command: {' '.join(command)}\n")
    
    # Execute the command and pass through the exit code
    result = subprocess.run(command)
    sys.exit(result.returncode)
