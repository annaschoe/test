"""
Minimal Flask application to test server connectivity
"""
from flask import Flask

# Create a minimal Flask app
app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello, World! Flask is working!"

@app.route('/test')
def test():
    return "Test route is working too!"

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Starting minimal Flask server to test connectivity")
    print("Try accessing:")
    print("  • http://127.0.0.1:8080")
    print("  • http://localhost:8080")
    print("=" * 60 + "\n")
    
    # Use a different port (8080) in case 5000 is blocked/used
    app.run(
        host='0.0.0.0',  # Listen on ALL network interfaces
        port=8080,       # Using port 8080 instead of 5000
        debug=True       # Enable debug mode to see any errors
    )
