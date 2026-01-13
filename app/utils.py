# app/utils.py

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
