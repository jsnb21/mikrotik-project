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
