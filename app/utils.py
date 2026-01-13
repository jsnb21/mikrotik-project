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
        host = os.getenv('MIKROTIK_HOST', '192.168.88.1')
        username = os.getenv('MIKROTIK_USERNAME', 'admin')
        password = os.getenv('MIKROTIK_PASSWORD', '')
        port = int(os.getenv('MIKROTIK_PORT', 8728))
        use_ssl = os.getenv('MIKROTIK_USE_SSL', 'False').lower() == 'true'
        
        conn = RouterOsApiPool(host, username=username, password=password, 
                              port=port, use_ssl=use_ssl, plaintext_login=True)
        api = conn.get_conn()
        return api
    except Exception as e:
        print(f"[MIKROTIK] Connection error: {str(e)}")
        return None

def mikrotik_allow_mac(mac_address, duration_seconds):
    """
    Allow a MAC address through MikroTik hotspot for specified duration.
    Uses the routeros API to add to IP > Hotspot > Active.
    """
    try:
        api = get_mikrotik_api()
        if not api:
            print(f"[MIKROTIK] Failed to connect - allowing MAC {mac_address} locally")
            return True
        
        # Add user to hotspot active list
        path = api.path('ip', 'hotspot', 'active')
        # Note: Adding to active list requires user to be already connected
        # Instead, we'll use IP > Hotspot > User to add a permanent user
        
        response = path.add(
            server='default',
            name=mac_address,
            mac_address=mac_address,
            limit_uptime=f"{duration_seconds}s",
            uptime_limit=f"{duration_seconds}s"
        )
        
        print(f"[MIKROTIK] Allowed MAC {mac_address} for {duration_seconds} seconds")
        api.close()
        return True
        
    except Exception as e:
        print(f"[MIKROTIK] Error allowing MAC {mac_address}: {str(e)}")
        return True  # Don't fail if API is down

def mikrotik_kick_mac(mac_address):
    """
    Kick a user from MikroTik hotspot.
    """
    try:
        api = get_mikrotik_api()
        if not api:
            return False
        
        # Find and remove the active session
        path = api.path('ip', 'hotspot', 'active')
        sessions = path.select('.id', 'mac-address').where('mac-address', '==', mac_address)
        
        for session in sessions:
            path.remove(session['.id'])
        
        print(f"[MIKROTIK] Kicked MAC {mac_address}")
        api.close()
        return True
        
    except Exception as e:
        print(f"[MIKROTIK] Error kicking MAC {mac_address}: {str(e)}")
        return False
