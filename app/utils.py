# app/utils.py

def mikrotik_allow_mac(mac_address, duration_seconds):
    """
    Mock function to communicate with MikroTik RouterOS.
    In production, this would use a library like librouteros or paramiko 
    to execute API commands.
    """
    print(f"[MIKROTIK] Allowing MAC {mac_address} for {duration_seconds} seconds")
    # Example logic:
    # api.path('ip', 'hotspot', 'active').add(mac=mac_address, limit_uptime=f"{duration_seconds}s")
    return True

def mikrotik_kick_mac(mac_address):
    """
    Mock function to kick a user from MikroTik.
    """
    print(f"[MIKROTIK] Kicking MAC {mac_address}")
    return True
