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
        
        api = RouterOsApiPool(host, username=username, password=password, 
                             port=port, use_ssl=use_ssl, plaintext_login=True)
        return api
    except Exception as e:
        print(f"[MIKROTIK] Connection error: {str(e)}")
        return None

def get_mikrotik_system_stats():
    """
    Mock function to fetch system resource usage from MikroTik.
    Returns: dict with cpu, memory, uptime, etc.
    """
    # In production: api.get_resource()
    return {
        "cpu_load": 15,
        "free_memory": 45000000,
        "total_memory": 64000000,
        "uptime": "2 weeks 4 days",
        "board_name": "hAP ac^2",
        "version": "6.48.6"
    }

def mikrotik_allow_mac(mac_address, duration_seconds):
    """Authorize a MAC for hotspot: create/update user and add bypass ip-binding."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        print(f"[MIKROTIK] Failed to connect - allowing MAC {mac_address} locally")
        return True

    hotspot_server = os.getenv('MIKROTIK_HOTSPOT_SERVER')  # Optional server name

    try:
        api = api_pool.get_api()
        users = api.get_resource('/ip/hotspot/user')
        ip_bindings = api.get_resource('/ip/hotspot/ip-binding')

        # Build payload for hotspot user
        payload = {
            'name': mac_address,
            'mac-address': mac_address,
            'limit-uptime': f"{duration_seconds}s",
        }
        if hotspot_server:
            payload['server'] = hotspot_server

        try:
            response = users.add(**payload)
            print(f"[MIKROTIK] Allowed MAC {mac_address} for {duration_seconds} seconds - ID: {response}")
        except Exception as e:
            msg = str(e)
            if 'already have user with this name' in msg:
                # Update existing user instead of failing
                existing = users.get(name=mac_address)
                if existing and isinstance(existing, list) and '.id' in existing[0]:
                    user_id = existing[0]['.id']
                    update_payload = {'limit-uptime': f"{duration_seconds}s"}
                    if hotspot_server:
                        update_payload['server'] = hotspot_server
                    users.set(id=user_id, **update_payload)
                    print(f"[MIKROTIK] Updated existing user {mac_address} with new uptime {duration_seconds}s")
                else:
                    print(f"[MIKROTIK] User exists but could not fetch id for update: {existing}")
            else:
                raise

        # Ensure IP binding bypass so the portal does not prompt again
        try:
            binding = ip_bindings.get(**{'mac-address': mac_address})
            if binding and isinstance(binding, list) and binding:
                binding_id = binding[0].get('.id')
                if binding_id:
                    ip_bindings.set(id=binding_id, **{'type': 'bypassed'})
                else:
                    print(f"[MIKROTIK] Warning: binding record missing .id: {binding[0]}")
            else:
                ip_bindings.add(**{'mac-address': mac_address, 'type': 'bypassed'})
            print(f"[MIKROTIK] Added/updated bypass binding for MAC {mac_address}")
        except Exception as e:
            print(f"[MIKROTIK] Warning: ip-binding bypass failed for {mac_address}: {str(e)}")

        return True
    except Exception as e:
        print(f"[MIKROTIK] Error allowing MAC {mac_address}: {str(e)}")
        return True  # Don't fail if API is down
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

def get_mikrotik_active_hotspot_users():
    """
    Mock function to fetch active hotspot users.
    Returns: list of dicts
    """
    # In production: api.path('ip', 'hotspot', 'active').get()
    return [
        {"user": "user1", "mac": "00:11:22:33:44:55", "uptime": "1h 30m", "bytes_in": 1024000, "bytes_out": 500000, "time_left": "30m"},
        {"user": "user2", "mac": "AA:BB:CC:DD:EE:FF", "uptime": "45m", "bytes_in": 204800, "bytes_out": 100000, "time_left": "2h 15m"},
        {"user": "user3", "mac": "11:22:33:44:55:66", "uptime": "5m", "bytes_in": 5000, "bytes_out": 2000, "time_left": "55m"}
    ]

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

def get_mikrotik_interface_traffic(interface_name="ether1"):
    """
    Mock function to get current traffic on an interface.
    """
    # In production: api.path('interface', 'monitor-traffic').get(...)
    import random
    return {
        "rx_bps": random.randint(1000, 10000000),
        "tx_bps": random.randint(1000, 5000000)
    }

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
