"""
Simple script to run the Flask application with better diagnostics
"""
import os
import socket
import webbrowser
import time
import platform
import sys
import traceback
import logging
import threading

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('app_errors.log')
    ]
)
logger = logging.getLogger(__name__)

# Ensure this script can find the flask_app package
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Ensure Flask finds templates in the 'templates' folder
from flask import Flask
Flask.template_folder = 'templates'

# Import Flask app from app.py in the root directory
try:
    from app import app
    
    # Add custom error handler for debugging template issues
    @app.errorhandler(500)
    def internal_error(error):
        error_tb = traceback.format_exc()
        logger.error(f"Internal Server Error: {error_tb}")
        return f"""
        <h1>Internal Server Error</h1>
        <p>The server encountered an error and could not complete your request.</p>
        <p>This error has been logged. Please check the server console or app_errors.log for details.</p>
        <pre>{error_tb}</pre>
        """, 500
        
except ImportError as e:
    logger.error(f"Failed to import Flask app: {e}")
    project_dir = os.path.dirname(os.path.abspath(__file__))
    app_path = os.path.join(project_dir, 'app.py')
    
    if not os.path.exists(app_path):
        sys.stderr.write(f"ERROR: The 'app.py' file does not exist at {app_path}\n")
        sys.stderr.write("Please ensure app.py exists with a Flask application instance named 'app'\n")
    else:
        sys.stderr.write(f"ERROR: Could not import Flask app! File exists but import failed: {e}\n")
        sys.stderr.write("Make sure app.py defines a Flask application instance named 'app'\n")
    sys.exit(1)

def get_ip():
    """Get the local IP address"""
    try:
        # Connect to public DNS to determine local IP used for internet connections
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        # Fallback to localhost if we can't determine IP
        return "127.0.0.1"

def open_browser(port):
    """Open the web browser to the login page"""
    try:
        webbrowser.open(f"http://127.0.0.1:{port}/login")
        print("\n✓ Browser opened automatically to login page")
    except Exception as e:
        print(f"\n✗ Could not open browser automatically: {e}")
        print("  Please open one of the URLs above manually in your browser")

if __name__ == '__main__':
    port = 5000
    local_ip = get_ip()

    # Force debug mode ON
    debug_mode = True
    os.environ['FLASK_DEBUG'] = '1'

    # --- ADD THIS BLOCK TO INITIALIZE DATABASE IF IT DOESN'T EXIST ---
    from app import app
    from database import init_db
    import os

    db_path = app.config['DATABASE_PATH']
    if not os.path.exists(db_path):
        print("Database not found, initializing...")
        init_db(app)
        print("Database initialized.")

    print("\n" + "=" * 60)
    print(f"Starting Flask server on ALL network interfaces (0.0.0.0:{port})")
    print(f"\nAccess the application in your web browser at:")
    print(f"  • From this computer: http://localhost:{port}")
    print(f"  • From other devices: http://{local_ip}:{port}")
    print(f"\nDEBUG MODE IS ENABLED")
    print(f"You can set FLASK_DEBUG=False to disable debug mode")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)

    # Start timer to open browser after a short delay (now to /login)
    threading.Timer(1.0, open_browser, args=[port]).start()

    # Run the app with debug mode ON
    app.run(
        host='0.0.0.0',  # Changed from 127.0.0.1 to listen on all network interfaces
        port=port,
        debug=debug_mode,
        threaded=True,
        use_reloader=False
    )
