# app/utils.py
import os

# Try to import routeros_api, but make it optional
try:
    from routeros_api import RouterOsApiPool
    ROUTEROS_AVAILABLE = True
except ImportError:
    ROUTEROS_AVAILABLE = False
    print("[WARNING] routeros_api not available. MikroTik API will be mocked.")

def get_mikrotik_api():
    """Connect to MikroTik RouterOS API"""
    if not ROUTEROS_AVAILABLE:
        return None
        
    try:
        # Accept both MIKROTIK_USERNAME and the older MIKROTIK_USER env var to avoid misconfigurations
        host = os.getenv('MIKROTIK_HOST', '192.168.88.1')
        username = os.getenv('MIKROTIK_USERNAME') or os.getenv('MIKROTIK_USER', 'admin')
        password = os.getenv('MIKROTIK_PASSWORD', '')
        port = int(os.getenv('MIKROTIK_PORT', 8728))
        use_ssl = os.getenv('MIKROTIK_USE_SSL', 'False').lower() == 'true'
        
        # Strip whitespace from credentials (common .env issue)
        username = username.strip()
        password = password.strip()
        
        # Show password hint for debugging (first char + *** + last char)
        pwd_hint = f"{password[0]}***{password[-1]}" if len(password) > 2 else "***"
        print(f"[DEBUG] MikroTik credentials: host={host}, user={username}, port={port}, ssl={use_ssl}, password={pwd_hint} (length={len(password)})")
        
        # Try API-SSL first (port 8729) if regular port fails
        connection_attempts = []
        
        # Attempt 1: Plaintext login first (most reliable for RouterOS API)
        connection_attempts.append(('plaintext', port, use_ssl, True))
        
        # Attempt 2: Try challenge-response (normal)
        if not use_ssl:
            connection_attempts.append(('normal', port, False, False))
        else:
            connection_attempts.append(('ssl', port, True, False))
            
        # Attempt 3: Try API-SSL on 8729 as fallback
        if port == 8728:
            connection_attempts.append(('ssl-8729', 8729, True, False))
        
        for attempt_name, attempt_port, attempt_ssl, plaintext in connection_attempts:
            try:
                print(f"[DEBUG] Trying connection method: {attempt_name}")
                if plaintext:
                    api = RouterOsApiPool(host, username=username, password=password, 
                                         port=attempt_port, use_ssl=attempt_ssl, plaintext_login=True)
                else:
                    api = RouterOsApiPool(host, username=username, password=password, 
                                         port=attempt_port, use_ssl=attempt_ssl)
                print(f"[DEBUG] ✓ Connected successfully using: {attempt_name}")
                return api
            except Exception as e:
                print(f"[DEBUG] ✗ Failed {attempt_name}: {str(e)[:100]}")
                continue
        
        raise Exception("All connection attempts failed")
    except Exception as e:
        print(f"[MIKROTIK] Connection error: {str(e)}")
        return None

def get_mikrotik_system_stats(api_pool=None):
    """
    Fetch system resource usage from MikroTik.
    Args:
        api_pool: Optional existing MikroTik API connection to reuse
    Returns: dict with cpu, memory, uptime, etc.
    Fallback: Returns mock data if connection fails.
    """
    mock_data = {
        "cpu_load": 15,
        "free_memory": 45000000,
        "total_memory": 64000000,
        "uptime": "Offline (Mock)",
        "board_name": "Unknown",
        "version": "Unknown"
    }

    # Use provided connection or create new one
    connection_provided = api_pool is not None
    if not connection_provided:
        api_pool = get_mikrotik_api()
    
    if not api_pool:
        return mock_data

    try:
        api = api_pool.get_api()
        resources = api.get_resource('/system/resource').get()
        routerboard = api.get_resource('/system/routerboard').get()
        
        if resources:
            res = resources[0]
            # Try to get router model name
            model = "MikroTik Router"
            if routerboard:
                model = routerboard[0].get('model', 'RouterBOARD')
            
            return {
                "cpu_load": res.get('cpu-load', 0),
                "free_memory": int(res.get('free-memory', 0)),
                "total_memory": int(res.get('total-memory', 0)),
                "uptime": res.get('uptime', '0s'),
                "board_name": model,
                "version": res.get('version', 'Unknown')
            }
    except Exception as e:
        print(f"[MIKROTIK] Error fetching system stats: {e}")
    finally:
        # Only disconnect if we created the connection
        if not connection_provided:
            try:
                api_pool.disconnect()
            except: pass
        
    return mock_data
def add_hotspot_user(name, password, profile, comment):
    """Adds a user to MikroTik Hotspot."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        print("[WARNING] Could not connect to MikroTik to add user.")
        return False
        
    try:
        api = api_pool.get_api()
        hotspot = api.get_resource('/ip/hotspot/user')
        # Check if user exists? Usually uniqueness is handled by RouterOS or we check before.
        # But here we just try to add.
        hotspot.add(
            name=name,
            password=password,
            profile=profile,
            comment=comment
        )
        api_pool.disconnect()
        return True
    except Exception as e:
        print(f"[MIKROTIK] Add User Error: {e}")
        if api_pool: 
            try: api_pool.disconnect()
            except: pass
        return False

def get_all_active_users():
    """Gets all active hotspot users."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        return []
        
    try:
        api = api_pool.get_api()
        active = api.get_resource('/ip/hotspot/active').get()
        api_pool.disconnect()
        return active
    except Exception as e:
        print(f"[MIKROTIK] Get Active Users Error: {e}")
        if api_pool: 
            try: api_pool.disconnect()
            except: pass
        return []

def set_hotspot_user_profile(username, profile_name):
    """Updates a user's profile (e.g., for FUP)."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        return False
        
    try:
        api = api_pool.get_api()
        hotspot_user = api.get_resource('/ip/hotspot/user')
        # Find user by name
        users = hotspot_user.get(name=username)
        if users:
            user_id = users[0]['id']
            hotspot_user.set(id=user_id, profile=profile_name)
            api_pool.disconnect()
            return True
        api_pool.disconnect()
        return False
    except Exception as e:
        print(f"[MIKROTIK] Set Profile Error: {e}")
        if api_pool: 
            try: api_pool.disconnect()
            except: pass
        return False

def mikrotik_allow_mac(mac_address, duration_seconds):
    """Authorize a MAC for hotspot: use IP binding with bypassed type for immediate access."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        print(f"[MIKROTIK] Failed to connect - allowing MAC {mac_address} locally")
        return True

    hotspot_server = os.getenv('MIKROTIK_HOTSPOT_SERVER', 'hotspot1')

    try:
        api = api_pool.get_api()
        ip_bindings = api.get_resource('/ip/hotspot/ip-binding')

        # Use IP binding with 'bypassed' type for immediate access
        # Note: Time limit enforcement must be handled by the application
        # since 'bypassed' bindings don't respect hotspot time limits
        try:
            binding = ip_bindings.get(**{'mac-address': mac_address})
            if binding and isinstance(binding, list) and binding:
                binding_id = binding[0].get('id') or binding[0].get('.id')
                if binding_id:
                    ip_bindings.set(id=binding_id, **{'type': 'bypassed', 'server': hotspot_server})
                    print(f"[MIKROTIK] Updated binding for MAC {mac_address} to bypassed")
                else:
                    print(f"[MIKROTIK] Warning: binding record missing id: {binding[0]}")
            else:
                ip_bindings.add(**{'mac-address': mac_address, 'type': 'bypassed', 'server': hotspot_server})
                print(f"[MIKROTIK] Added bypassed binding for MAC {mac_address}")
        except Exception as e:
            print(f"[MIKROTIK] Error setting up IP binding: {str(e)}")

        return True
    except Exception as e:
        print(f"[MIKROTIK] Error allowing MAC {mac_address}: {str(e)}")
        return True  # Don't fail if API is down
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass

def mikrotik_revoke_mac(mac_address):
    """Revoke access for a MAC address by removing IP binding."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        print(f"[MIKROTIK] Failed to connect - cannot revoke MAC {mac_address}")
        return False

    try:
        api = api_pool.get_api()
        ip_bindings = api.get_resource('/ip/hotspot/ip-binding')

        # Remove IP binding to revoke access
        try:
            binding = ip_bindings.get(**{'mac-address': mac_address})
            if binding and isinstance(binding, list) and binding:
                binding_id = binding[0].get('id') or binding[0].get('.id')
                if binding_id:
                    ip_bindings.remove(id=binding_id)
                    print(f"[MIKROTIK] Revoked access for MAC {mac_address}")
                    return True
            print(f"[MIKROTIK] No binding found for MAC {mac_address}")
            return False
        except Exception as e:
            print(f"[MIKROTIK] Error revoking MAC {mac_address}: {str(e)}")
            return False
    except Exception as e:
        print(f"[MIKROTIK] Error connecting to revoke MAC {mac_address}: {str(e)}")
        return False
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass

def get_mac_from_active_session(client_ip):
    """Get MAC address from MikroTik active hotspot sessions by client IP."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        return None
    
    try:
        api = api_pool.get_api()
        active = api.get_resource('/ip/hotspot/active')
        sessions = active.get(**{'address': client_ip})
        
        if sessions and isinstance(sessions, list) and len(sessions) > 0:
            mac = sessions[0].get('mac-address')
            print(f"[MIKROTIK] Found active session for IP {client_ip}: MAC {mac}")
            return mac
    except Exception as e:
        print(f"[MIKROTIK] Error looking up active session for IP {client_ip}: {str(e)}")
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass
    
    return None

def get_mikrotik_active_hotspot_users(api_pool=None):
    """
    Fetch active hotspot users from MikroTik.
    Args:
        api_pool: Optional existing MikroTik API connection to reuse
    Returns: list of dicts.
    Fallback: Returns mock data if connection fails.
    """
    mock_data = [
        {"user": "user1 (mock)", "mac": "00:11:22:33:44:55", "uptime": "1h 30m", "bytes_in": 1024000, "bytes_out": 500000, "time_left": "30m"},
    ]

    # Use provided connection or create new one
    connection_provided = api_pool is not None
    if not connection_provided:
        api_pool = get_mikrotik_api()
    
    if not api_pool:
        return mock_data

    try:
        api = api_pool.get_api()
        active = api.get_resource('/ip/hotspot/active').get()
        users_list = []
        
        for idx, session in enumerate(active):
            if idx >= 10: break # Limit to 10
            users_list.append({
                "user": session.get('user', 'Unknown'),
                "mac": session.get('mac-address', ''),
                "uptime": session.get('uptime', '0s'),
                "bytes_in": int(session.get('bytes-in', 0)),
                "bytes_out": int(session.get('bytes-out', 0)),
                "time_left": session.get('session-time-left', 'Unknown')
            })
        return users_list
    except Exception as e:
        print(f"[MIKROTIK] Error fetching active users: {e}")
    finally:
        # Only disconnect if we created the connection
        if not connection_provided:
            try:
                api_pool.disconnect()
            except: pass
        
    return mock_data

def get_income_stats():
    """
    Mock function to get income statistics.
    Returns: dict with daily and monthly data
    """
    return {
        "earned_today": 900,
        "earned_month": 22000,
        "earned_year": 91500,
        "average_daily": 657,
        "daily": [500, 600, 450, 700, 800, 650, 900], # Last 7 days
        "monthly": [15000, 18000, 16500, 20000, 22000], # Last 5 months
        "labels_daily": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        "labels_monthly": ["Jan", "Feb", "Mar", "Apr", "May"]
    }

def get_mikrotik_interface_traffic(interface_name=None, api_pool=None):
    """
    Get current traffic on an interface.
    Args:
        interface_name: Optional interface name (default from env var)
        api_pool: Optional existing MikroTik API connection to reuse
    Fallback: Returns random mock data if connection fails.
    """
    import random
    mock_data = {
        "rx_bps": random.randint(1000, 1000000),
        "tx_bps": random.randint(1000, 500000)
    }

    if not interface_name:
        interface_name = os.getenv('MIKROTIK_WAN_INTERFACE', 'ether1')

    # Use provided connection or create new one
    connection_provided = api_pool is not None
    if not connection_provided:
        api_pool = get_mikrotik_api()
    
    if not api_pool:
        return mock_data

    try:
        api = api_pool.get_api()
        # Using monitor-traffic command
        # Syntax: /interface monitor-traffic [find name=ether1] once
        traffic = api.get_resource('/interface').call('monitor-traffic', {
            'interface': interface_name,
            'once': 'true'
        })
        
        if traffic:
            t = traffic[0]
            return {
                "rx_bps": int(t.get('rx-bits-per-second', 0)),
                "tx_bps": int(t.get('tx-bits-per-second', 0))
            }
    except Exception as e:
        print(f"[MIKROTIK] Error fetching traffic for {interface_name}: {e}")
    finally:
        # Only disconnect if we created the connection
        if not connection_provided:
            try:
                api_pool.disconnect()
            except: pass
        
    return mock_data

def mikrotik_kick_mac(mac_address):
    """Remove an active hotspot session for a MAC."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        return False

    try:
        api = api_pool.get_api()
        active = api.get_resource('/ip/hotspot/active')
        sessions = active.get(**{'mac-address': mac_address})

        for session in sessions:
            active.remove(id=session['.id'])

        print(f"[MIKROTIK] Kicked MAC {mac_address}")
        return True
    except Exception as e:
        print(f"[MIKROTIK] Error kicking MAC {mac_address}: {str(e)}")
        return False
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass
