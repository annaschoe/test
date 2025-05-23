"""
Helper script to restart Flask application properly
"""
import os
import sys
import time
import subprocess
import signal
import psutil

def kill_process_on_port(port=5000):
    """Kill any process running on the specified port"""
    for proc in psutil.process_iter(['pid', 'name', 'connections']):
        try:
            for conn in proc.connections():
                if conn.laddr.port == port:
                    print(f"Killing process {proc.info['pid']} ({proc.info['name']}) on port {port}")
                    if sys.platform == 'win32':
                        subprocess.run(['taskkill', '/F', '/PID', str(proc.info['pid'])], 
                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    else:
                        os.kill(proc.info['pid'], signal.SIGTERM)
                    time.sleep(1)  # Give it time to shut down
                    return True
        except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
            continue
    return False

if __name__ == "__main__":
    # Kill any existing processes
    kill_process_on_port(5000)
    
    # Clear Python's import cache
    print("Clearing Python's module cache")
    for module in list(sys.modules.keys()):
        if module.startswith('flask_app'):
            del sys.modules[module]
    
    # Start the Flask app
    print("Starting Flask application")
    flask_app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 
                                 'flask_app', 'app.py')
    
    # Set environment variables for debugging
    env = os.environ.copy()
    env['FLASK_DEBUG'] = '1'
    
    # Start the Flask app in a new process
    subprocess.Popen([sys.executable, flask_app_path], env=env)
    
    print("Flask application restarted!")
