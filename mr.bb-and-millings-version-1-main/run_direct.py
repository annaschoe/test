"""
Simple script to run the Flask application with a direct import
"""
import os
import socket
import webbrowser
import sys
import threading

# Add the current directory to the Python path for imports
project_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.append(project_dir)

# Direct import - no try/except that might cause confusion
from app import app

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

if __name__ == '__main__':
    port = 5000
    local_ip = get_ip()

    # Force debug mode ON
    debug_mode = True
    os.environ['FLASK_DEBUG'] = '1'

    print("\n" + "=" * 60)
    print(f"Starting Flask server on ALL network interfaces (0.0.0.0:{port})")
    print(f"\nAccess the application in your web browser at:")
    print(f"  • From this computer: http://localhost:{port}")
    print(f"  • From other devices: http://{local_ip}:{port}")
    print(f"\nDEBUG MODE IS ENABLED")
    print(f"You can set FLASK_DEBUG=False to disable debug mode")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 60)

    # Try to open the browser automatically with a delay
    def open_browser():
        try:
            webbrowser.open(f"http://localhost:{port}")
            print("\n✓ Browser opened automatically to application")
        except Exception as e:
            print(f"\n✗ Could not open browser automatically: {e}")
            print("  Please open one of the URLs above manually in your browser")

    # Start timer to open browser after a short delay
    threading.Timer(1.5, open_browser).start()

    # Run the app with debug mode ON
    app.run(
        host='0.0.0.0',  # Listen on all network interfaces
        port=port,
        debug=debug_mode,
        threaded=True,
        use_reloader=False
    )
