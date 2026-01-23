# MikroTik Connection Troubleshooting Guide

## Issue: "No Connection to MikroTik Router"

### Quick Diagnostic Steps

1. **Run the diagnostic script on your Raspberry Pi:**
   ```bash
   cd /path/to/mikrotik-project
   python3 test_mikrotik_connection.py
   ```

2. **Check your .env file configuration:**
   ```bash
   cat .env | grep MIKROTIK
   ```
   
   Required settings:
   - `MIKROTIK_HOST` - Router IP (e.g., 192.168.88.1)
   - `MIKROTIK_USERNAME` - Usually "admin"
   - `MIKROTIK_PASSWORD` - Your router password
   - `MIKROTIK_PORT` - Usually 8728
   - `MIKROTIK_USE_SSL` - Usually False

### Common Causes & Solutions

#### 1. MikroTik API Service Not Enabled
**Solution:**
- Open WinBox and connect to your router
- Go to: `IP` → `Services`
- Find the `api` service
- Make sure it's **enabled** and listening on port 8728
- Available from: Set to `0.0.0.0/0` or your Raspberry Pi's IP

#### 2. Wrong IP Address
**Solution:**
- Verify router IP: Open WinBox and check the IP
- Update `.env` file with correct IP:
  ```
  MIKROTIK_HOST=192.168.88.1
  ```

#### 3. Incorrect Username/Password
**Solution:**
- Test credentials in WinBox first
- Update `.env` file:
  ```
  MIKROTIK_USERNAME=admin
  MIKROTIK_PASSWORD=your_password_here
  ```
- Remove any extra spaces or quotes

#### 4. Firewall Blocking Connection
**Solution:**
- In WinBox, go to: `IP` → `Firewall` → `Filter Rules`
- Make sure there's no rule blocking port 8728 from your Pi's IP
- Or add an accept rule:
  ```
  Chain: input
  Protocol: tcp
  Dst. Port: 8728
  Src. Address: [Your Pi IP]/32
  Action: accept
  ```

#### 5. Network Connectivity Issue
**Test connectivity from Raspberry Pi:**
```bash
# Test if router is reachable
ping 192.168.88.1

# Test if port 8728 is open
nc -zv 192.168.88.1 8728
# or
telnet 192.168.88.1 8728
```

#### 6. Missing Python Package
**Solution:**
```bash
pip install routeros-api
```

### Verify Working Connection

Once fixed, you should see in the Flask logs:
```
[DEBUG] MikroTik credentials: host=192.168.88.1, user=admin, port=8728, ssl=False...
[DEBUG] Trying connection method: plaintext
[DEBUG] ✓ Connected successfully using: plaintext
```

---

## Issue: Server Control Buttons Not Working

### Symptoms
- Clicking Start/Stop/Restart buttons shows "Connection Refused"
- Buttons don't respond

### Solutions

#### 1. Server Not Running on Expected Address
Make sure Flask is running on `0.0.0.0:5000`:
```bash
# Check if process is listening
netstat -tlnp | grep 5000

# Or use
ss -tlnp | grep 5000
```

#### 2. CSRF Protection Issue
The POST requests need proper headers. Already fixed in code.

#### 3. JavaScript Not Loading
Check browser console (F12) for errors.

#### 4. Try Manual Server Control Instead
Instead of using buttons, use terminal:
```bash
# To stop the server
pkill -f "python.*run.py"

# To start the server
python3 run.py

# To restart
pkill -f "python.*run.py" && sleep 2 && python3 run.py &
```

---

## Additional Debugging

### Enable Detailed Logging
In `app/utils.py`, the debug messages are already enabled. Check Flask console output.

### View Real-Time Logs
```bash
# If running as a service
journalctl -u mikrotik-flask -f

# If running directly
python3 run.py
```

### Test API Manually
Create a test file `test_api.py`:
```python
from routeros_api import RouterOsApiPool

api = RouterOsApiPool('192.168.88.1', username='admin', password='12345', port=8728, plaintext_login=True)
api_instance = api.get_api()
resource = api_instance.get_resource('/system/resource')
print(resource.get())
api.disconnect()
```

Run it:
```bash
python3 test_api.py
```

---

## Still Having Issues?

1. Share the output of `test_mikrotik_connection.py`
2. Check Flask console logs
3. Verify MikroTik RouterOS version (v6.x or v7.x)
4. Ensure Raspberry Pi and MikroTik are on the same network
