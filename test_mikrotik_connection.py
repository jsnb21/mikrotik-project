#!/usr/bin/env python3
"""
Diagnostic script to test MikroTik router connection from Raspberry Pi
Run this on your Raspberry Pi to diagnose connection issues
"""

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

print("=" * 60)
print("MikroTik Connection Diagnostic Tool")
print("=" * 60)

# Read configuration
host = os.getenv('MIKROTIK_HOST', '192.168.88.1')
username = os.getenv('MIKROTIK_USERNAME') or os.getenv('MIKROTIK_USER', 'admin')
password = os.getenv('MIKROTIK_PASSWORD', '')
port = int(os.getenv('MIKROTIK_PORT', 8728))
use_ssl = os.getenv('MIKROTIK_USE_SSL', 'False').lower() == 'true'

print(f"\n[CONFIG] Reading from .env file:")
print(f"  Host: {host}")
print(f"  Username: {username}")
print(f"  Password: {'*' * len(password)} (length: {len(password)})")
print(f"  Port: {port}")
print(f"  SSL: {use_ssl}")

# Test 1: Check if routeros_api is installed
print(f"\n[TEST 1] Checking if routeros_api is installed...")
try:
    from routeros_api import RouterOsApiPool
    print("  ✓ routeros_api is installed")
except ImportError as e:
    print("  ✗ routeros_api is NOT installed")
    print(f"  Error: {e}")
    print("\n  Run: pip install routeros-api")
    sys.exit(1)

# Test 2: Network connectivity
print(f"\n[TEST 2] Testing network connectivity to {host}:{port}...")
import socket
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    result = sock.connect_ex((host, port))
    sock.close()
    
    if result == 0:
        print(f"  ✓ Port {port} is OPEN and reachable")
    else:
        print(f"  ✗ Port {port} is CLOSED or unreachable")
        print(f"  Error code: {result}")
        print("\n  Possible causes:")
        print("  - MikroTik router is not running")
        print("  - Wrong IP address in .env file")
        print("  - API service not enabled on router")
        print("  - Firewall blocking port 8728")
        print("\n  To enable API on MikroTik:")
        print("  1. Open WinBox")
        print("  2. Go to IP > Services")
        print("  3. Enable 'api' service")
except socket.gaierror:
    print(f"  ✗ Cannot resolve hostname: {host}")
except Exception as e:
    print(f"  ✗ Network error: {e}")

# Test 3: Try API connection
print(f"\n[TEST 3] Attempting API connection...")
connection_methods = [
    ('plaintext', port, use_ssl, True),
    ('normal', port, False, False),
]

if port == 8728:
    connection_methods.append(('ssl-8729', 8729, True, False))

api = None
for method_name, test_port, test_ssl, plaintext in connection_methods:
    try:
        print(f"\n  Trying method: {method_name} (port={test_port}, ssl={test_ssl}, plaintext={plaintext})")
        
        if plaintext:
            api = RouterOsApiPool(
                host, 
                username=username, 
                password=password,
                port=test_port, 
                use_ssl=test_ssl, 
                plaintext_login=True
            )
        else:
            api = RouterOsApiPool(
                host, 
                username=username, 
                password=password,
                port=test_port, 
                use_ssl=test_ssl
            )
        
        print(f"  ✓ SUCCESS! Connected using {method_name}")
        break
    except Exception as e:
        print(f"  ✗ Failed: {str(e)[:150]}")
        api = None
        continue

# Test 4: Query router info
if api:
    print(f"\n[TEST 4] Querying router information...")
    try:
        api_instance = api.get_api()
        resource_system = api_instance.get_resource('/system/resource')
        system_info = resource_system.get()
        
        if system_info:
            info = system_info[0]
            print(f"  ✓ Router Model: {info.get('board-name', 'N/A')}")
            print(f"  ✓ Version: {info.get('version', 'N/A')}")
            print(f"  ✓ Uptime: {info.get('uptime', 'N/A')}")
            print(f"  ✓ CPU Load: {info.get('cpu-load', 'N/A')}%")
            print(f"\n  ✓✓✓ CONNECTION SUCCESSFUL ✓✓✓")
        else:
            print("  ⚠ Connected but no data returned")
    except Exception as e:
        print(f"  ✗ Error querying router: {e}")
    finally:
        try:
            api.disconnect()
        except:
            pass
else:
    print(f"\n[RESULT] ✗✗✗ ALL CONNECTION ATTEMPTS FAILED ✗✗✗")
    print("\nTroubleshooting steps:")
    print("1. Verify router IP address is correct")
    print("2. Check username and password in .env file")
    print("3. Ensure MikroTik API service is enabled (IP > Services > api)")
    print("4. Try connecting from Winbox to verify router is accessible")
    print("5. Check if firewall is blocking port 8728")
    print("6. Verify Raspberry Pi is on the same network as the router")

print("\n" + "=" * 60)
