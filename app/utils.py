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
    """Connect to MikroTik RouterOS API.
    Prefers Flask app config if available; falls back to environment variables.
    """
    if not ROUTEROS_AVAILABLE:
        return None

    try:
        # Prefer Flask app config when running inside app context
        host = None
        username = None
        password = None
        port = None
        use_ssl = None

        try:
            from flask import current_app, has_app_context
            if has_app_context():
                cfg = current_app.config
                host = cfg.get('MIKROTIK_HOST')
                username = cfg.get('MIKROTIK_USERNAME')
                password = cfg.get('MIKROTIK_PASSWORD')
                port = cfg.get('MIKROTIK_PORT')
                use_ssl = cfg.get('MIKROTIK_USE_SSL')
        except Exception:
            # Not in a Flask context; will use env vars
            pass

        # Fallback to environment variables if config missing
        host = host or os.getenv('MIKROTIK_HOST', '192.168.88.1')
        username = username or os.getenv('MIKROTIK_USERNAME', 'admin')
        password = password or os.getenv('MIKROTIK_PASSWORD', '')
        port = int(port or os.getenv('MIKROTIK_PORT', 8728))
        use_ssl = bool(use_ssl) if use_ssl is not None else (os.getenv('MIKROTIK_USE_SSL', 'False').lower() == 'true')

        # Strip accidental whitespace from credentials
        username = (username or '').strip()
        password = (password or '').strip()

        # Show password hint for debugging (first char + *** + last char)
        pwd_hint = f"{password[0]}***{password[-1]}" if len(password) > 2 else "***"
        print(f"[DEBUG] MikroTik credentials: host={host}, user={username}, port={port}, ssl={use_ssl}, password={pwd_hint} (length={len(password)})")

        # Connection strategies
        connection_attempts = []
        # Attempt 1: Plaintext login (most reliable for RouterOS API)
        connection_attempts.append(('plaintext', port, use_ssl, True))
        # Attempt 2: Challenge-response
        if not use_ssl:
            connection_attempts.append(('normal', port, False, False))
        else:
            connection_attempts.append(('ssl', port, True, False))
        # Attempt 3: API-SSL default port fallback
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
                print(f"[DEBUG] ✗ Failed {attempt_name}: {str(e)[:200]}")
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
    """Revoke access for a MAC address by removing IP binding.
    Returns True if binding was found and removed, or if MAC not in RouterOS (already gone).
    """
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
            # Binding not found in RouterOS - it was already removed or never existed
            # This is OK, just log and return True (consider it revoked)
            print(f"[MIKROTIK] MAC {mac_address} not found in bindings (already revoked or expired)")
            return True
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

def get_mac_from_arp(ip_address):
    """
    Get MAC address from MikroTik ARP table by IP address.
    """
    api_pool = get_mikrotik_api()
    if not api_pool:
        # Fallback for development/testing when no router is connected
        print(f"[MIKROTIK] Connection unavailable, cannot resolve ARP for {ip_address}")
        return None

    try:
        api = api_pool.get_api()
        # Look up in ARP table
        arp_entries = api.get_resource('/ip/arp').get(**{'address': ip_address})
        
        if arp_entries and isinstance(arp_entries, list) and len(arp_entries) > 0:
            mac = arp_entries[0].get('mac-address')
            print(f"[MIKROTIK] Found ARP entry for IP {ip_address}: MAC {mac}")
            return mac
        
        print(f"[MIKROTIK] No ARP entry found for IP {ip_address}")
    except Exception as e:
        print(f"[MIKROTIK] Error looking up ARP for IP {ip_address}: {str(e)}")
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
    mock_data = []

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

def get_mikrotik_health(api_pool=None):
    """Fetch system health (temperature/voltage). Returns dict with optional temperature."""
    mock = {"temperature": None, "voltage": None}

    connection_provided = api_pool is not None
    if not connection_provided:
        api_pool = get_mikrotik_api()
    if not api_pool:
        return mock

    try:
        api = api_pool.get_api()
        health_res = api.get_resource('/system/health').get()
        if health_res:
            first = health_res[0]
            # RouterOS uses either 'temperature' or 'board-temperature'
            temp = first.get('temperature') or first.get('board-temperature')
            voltage = first.get('voltage') or first.get('board-voltage')
            return {
                "temperature": temp,
                "voltage": voltage,
            }
    except Exception as e:
        print(f"[MIKROTIK] Error fetching health: {e}")
    finally:
        if not connection_provided:
            try:
                api_pool.disconnect()
            except:  # noqa: E722
                pass

    return mock


def get_server_stats():
    """Get server PC statistics from actual system data (Raspberry Pi or Linux)."""
    import subprocess
    import psutil
    
    # Mock data fallback
    mock_data = {
        "model": "Raspberry Pi 4 Model B",
        "cpu_model": "Quad-core Cortex-A72 (ARM v8) 64-bit SoC @ 1.5GHz",
        "cpu_usage": 12.5,
        "cpu_cores": 4,
        "total_memory": 4096,  # 4GB RAM in MB
        "used_memory": 1024,
        "free_memory": 3072,
        "uptime": "2d 14h 32m",
        "temperature": "48.2°C",
        "os": "Raspberry Pi OS (64-bit)",
        "kernel": "Linux 6.1.21-v8+"
    }
    
    try:
        data = {}
        
        # Get Raspberry Pi Model
        try:
            with open('/proc/device-tree/model', 'r') as f:
                data['model'] = f.read().strip('\x00')
        except:
            data['model'] = "Unknown Device"
        
        # Get CPU Model from /proc/cpuinfo
        try:
            with open('/proc/cpuinfo', 'r') as f:
                cpuinfo = f.read()
                # Extract hardware info
                for line in cpuinfo.split('\n'):
                    if line.startswith('Hardware'):
                        data['cpu_model'] = line.split(':', 1)[1].strip()
                        break
                else:
                    data['cpu_model'] = "ARM Processor"
        except:
            data['cpu_model'] = "Unknown CPU"
        
        # Get CPU cores count
        data['cpu_cores'] = psutil.cpu_count(logical=False)
        
        # Get CPU usage percentage
        data['cpu_usage'] = psutil.cpu_percent(interval=0.1)
        
        # Get Memory info (in MB)
        memory = psutil.virtual_memory()
        data['total_memory'] = int(memory.total / (1024 * 1024))
        data['used_memory'] = int(memory.used / (1024 * 1024))
        data['free_memory'] = int(memory.available / (1024 * 1024))
        
        # Get Uptime
        try:
            with open('/proc/uptime', 'r') as f:
                uptime_seconds = int(float(f.read().split()[0]))
                days, remainder = divmod(uptime_seconds, 86400)
                hours, remainder = divmod(remainder, 3600)
                minutes, _ = divmod(remainder, 60)
                
                if days > 0:
                    data['uptime'] = f"{days}d {hours}h {minutes}m"
                elif hours > 0:
                    data['uptime'] = f"{hours}h {minutes}m"
                else:
                    data['uptime'] = f"{minutes}m"
        except:
            data['uptime'] = "0m"
        
        # Get CPU Temperature (Raspberry Pi specific)
        data['temperature'] = "N/A"
        try:
            # Try Raspberry Pi thermal zone
            with open('/sys/class/thermal/thermal_zone0/temp', 'r') as f:
                temp_millidegrees = int(f.read().strip())
                temp_celsius = temp_millidegrees / 1000
                data['temperature'] = f"{temp_celsius:.1f}°C"
        except:
            try:
                # Alternative: Try vcgencmd (if available on RPi)
                result = subprocess.run(['vcgencmd', 'measure_temp'], 
                                      capture_output=True, text=True, timeout=2)
                if result.returncode == 0:
                    # Output: temp=48.2'C
                    temp_str = result.stdout.strip().split('=')[1]
                    data['temperature'] = temp_str
            except:
                pass
        
        # Get OS Info
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = f.read()
                for line in os_info.split('\n'):
                    if line.startswith('PRETTY_NAME'):
                        data['os'] = line.split('=', 1)[1].strip().strip('"')
                        break
                else:
                    data['os'] = "Linux"
        except:
            data['os'] = "Linux"
        
        # Get Kernel version
        try:
            result = subprocess.run(['uname', '-r'], 
                                  capture_output=True, text=True, timeout=2)
            data['kernel'] = result.stdout.strip()
        except:
            data['kernel'] = "Unknown"
        
        return data
    
    except Exception as e:
        print(f"[ERROR] Failed to get server stats: {str(e)}")
        return mock_data

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

def get_mac_from_arp(ip_address):
    """Get MAC address from MikroTik ARP table by IP address."""
    api_pool = get_mikrotik_api()
    if not api_pool:
        return None
    
    try:
        api = api_pool.get_api()
        arp = api.get_resource('/ip/arp')
        entries = arp.get(**{'address': ip_address})
        
        if entries and isinstance(entries, list) and len(entries) > 0:
            mac = entries[0].get('mac-address')
            print(f"[MIKROTIK] Found ARP entry for IP {ip_address}: MAC {mac}")
            return mac
    except Exception as e:
        print(f"[MIKROTIK] Error looking up ARP for IP {ip_address}: {str(e)}")
    finally:
        try:
            api_pool.disconnect()
        except Exception:
            pass
    
    return None
