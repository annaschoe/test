"""
Tool to diagnose network connectivity issues
"""
import socket
import subprocess
import sys
import os

def check_port_availability(port):
    """Check if a port is available"""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = s.connect_ex(('127.0.0.1', port))
    is_available = result != 0
    s.close()
    return is_available

def get_ip_addresses():
    """Get all network interfaces and IP addresses"""
    ip_addresses = []
    try:
        # This works on both Windows and Unix
        interfaces = socket.getaddrinfo(socket.gethostname(), None)
        for interface in interfaces:
            ip = interface[4][0]
            # Filter out IPv6 addresses and localhost
            if ':' not in ip and ip != '127.0.0.1':
                ip_addresses.append(ip)
    except Exception as e:
        print(f"Error getting IP addresses: {e}")
    
    return list(set(ip_addresses))  # Remove duplicates

def check_firewall():
    """Check if Windows Firewall is enabled"""
    if sys.platform != 'win32':
        return "Not running on Windows"
    
    try:
        result = subprocess.run(
            ['netsh', 'advfirewall', 'show', 'allprofiles'], 
            capture_output=True, 
            text=True
        )
        return result.stdout
    except Exception as e:
        return f"Error checking firewall: {e}"

def ping_test(host="8.8.8.8"):
    """Test if the network is working by pinging Google's DNS"""
    param = '-n' if sys.platform.lower() == 'win32' else '-c'
    command = ['ping', param, '1', host]
    try:
        return subprocess.call(
            command, 
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        ) == 0
    except Exception:
        return False

if __name__ == "__main__":
    print("\n===== NETWORK DIAGNOSTICS =====\n")
    
    print("Checking network connectivity...")
    if ping_test():
        print("✓ Network is connected")
    else:
        print("✗ Network connection issue detected")
    
    print("\nChecking available ports...")
    test_ports = [5000, 8080, 8000]
    for port in test_ports:
        if check_port_availability(port):
            print(f"✓ Port {port} is available")
        else:
            print(f"✗ Port {port} is already in use (try a different port)")
    
    print("\nAvailable IP addresses on this computer:")
    for ip in get_ip_addresses():
        print(f"• {ip}")
    
    print("\nFirewall status:")
    print(check_firewall())
    
    print("\n===== RECOMMENDATIONS =====")
    print("1. Try using a different port if 5000 is in use")
    print("2. Check if Python is allowed through your firewall")
    print("3. Try accessing your app at http://127.0.0.1:8080 after running minimal.py")
    print("4. If nothing works, try temporarily disabling your firewall")
    
    input("\nPress Enter to exit...")
