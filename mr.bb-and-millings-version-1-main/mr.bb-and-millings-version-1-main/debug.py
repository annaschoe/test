"""
Debug script to diagnose server connection issues
"""
import socket
import os
import sys
import subprocess
import platform

def check_port(port=5000):
    """Check if the port is already in use"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        result = sock.connect_ex(('127.0.0.1', port))
        if result == 0:
            print(f"✓ Port {port} is open (something is running there)")
        else:
            print(f"✗ Port {port} is not open (nothing is running there)")
        sock.close()
    except Exception as e:
        print(f"Error checking port: {e}")

def check_firewall():
    """Check if firewall might be blocking connections"""
    if platform.system() == "Windows":
        print("\nChecking Windows Firewall status...")
        try:
            result = subprocess.run(["netsh", "advfirewall", "show", "currentprofile"], 
                                   capture_output=True, text=True)
            print(result.stdout)
        except Exception as e:
            print(f"Error checking firewall: {e}")

def get_ip_addresses():
    """Get all IP addresses of this computer"""
    print("\nIP addresses for this computer:")
    try:
        hostname = socket.gethostname()
        print(f"Hostname: {hostname}")
        
        # Get all addresses
        addresses = socket.getaddrinfo(hostname, None)
        ips = set()
        for addr in addresses:
            ip = addr[4][0]
            if ip != '127.0.0.1' and ':' not in ip:  # Skip localhost and IPv6
                ips.add(ip)
        
        for ip in ips:
            print(f"IP address: {ip} (Try http://{ip}:5000)")
            
        print("\nYou can also try: http://localhost:5000")
    except Exception as e:
        print(f"Error getting IP addresses: {e}")

if __name__ == "__main__":
    print("--- Flask Server Connectivity Check ---")
    check_port()
    get_ip_addresses()
    check_firewall()
    
    print("\nPossible issues and solutions:")
    print("1. Make sure you're running the app with 'python run.py'")
    print("2. Try accessing the app using the IP addresses above")
    print("3. Check if Windows Firewall is blocking Python")
    print("4. If running in a virtual environment, make sure it's activated")
    print("5. Try adding a rule to Windows Firewall to allow Python on port 5000")
