# MikroTik Hotspot Files
# ========================

These files should be uploaded to your MikroTik router's hotspot folder.

## How It Works

1. **User connects to WiFi** - Phone is captured by MikroTik hotspot
2. **login.html is shown** - MikroTik serves this page directly
3. **User enters voucher code** - The page calls Flask API to activate the voucher
4. **Hotspot user is created** - Flask creates the user in MikroTik via API
5. **Form submits to MikroTik** - The voucher code is used as username/password
6. **User is authenticated** - MikroTik logs them in and grants internet

The login.html page is designed to work even if the phone can't reach the Flask server directly - it will fallback to trying direct MikroTik login.

## How to Upload

### Method 1: Using Winbox (Recommended)
1. Open Winbox and connect to your router
2. Go to **Files** (left sidebar)
3. Navigate to the **hotspot** folder
4. Drag and drop these files into the folder (or right-click → Upload)
5. Overwrite existing files when prompted

### Method 2: Using SCP
```bash
scp login.html admin@192.168.88.1:/hotspot/
scp redirect.html admin@192.168.88.1:/hotspot/
scp rlogin.html admin@192.168.88.1:/hotspot/
scp logout.html admin@192.168.88.1:/hotspot/
scp status.html admin@192.168.88.1:/hotspot/
scp error.html admin@192.168.88.1:/hotspot/
```

### Method 3: Using FTP
1. Enable FTP on your router: `/ip service enable ftp`
2. Connect via FTP to 192.168.88.1
3. Upload files to the /hotspot folder

## Files Included

| File | Purpose |
|------|---------|
| `login.html` | Main login page with embedded form + API call to Flask |
| `redirect.html` | Redirect page after login |
| `rlogin.html` | Re-login page |
| `logout.html` | Shown when user logs out |
| `status.html` | Shows connection status and remaining time |
| `error.html` | Shows error messages |

## Configuration

These files are configured for:
- **Server:** 192.168.88.21
- **Port:** 5001

If your server IP or port is different, edit `login.html` and change:
```javascript
var SERVER = 'http://192.168.88.21:5001';
```

## MikroTik Variables Used

The files use these MikroTik template variables:
- `$(mac)` - Client MAC address
- `$(ip)` - Client IP address
- `$(username)` - Username (voucher code)
- `$(link-login-only)` - URL to submit login credentials
- `$(link-orig)` - Original URL the client tried to access
- `$(error)` - Error message
- `$(uptime)` - Session uptime
- `$(bytes-in)` / `$(bytes-out)` - Data usage

## Required MikroTik Commands

After uploading the files, run these commands in MikroTik Terminal to allow the phone to reach the Flask server:

```
# CRITICAL: Add server to walled garden (allows HTTP requests before login)
/ip hotspot walled-garden ip add dst-address=192.168.88.21 action=accept comment="Pisonet Server"

# Add server hostname to walled garden
/ip hotspot walled-garden add dst-host="192.168.88.21" action=allow comment="Pisonet IP"
/ip hotspot walled-garden add dst-host="neuronet.ai" action=allow comment="Pisonet Domain"

# Add DNS entry for domain
/ip dns static add name=neuronet.ai address=192.168.88.21 comment="Pisonet Server"

# Allow connectivity checks (for Android/iOS captive portal detection)
/ip hotspot walled-garden add dst-host="connectivitycheck.gstatic.com" action=allow comment="Android check"
/ip hotspot walled-garden add dst-host="clients3.google.com" action=allow comment="Android check 2"
/ip hotspot walled-garden add dst-host="captive.apple.com" action=allow comment="iOS check"

# Test connection from router (should show status:finished)
/tool fetch url="http://192.168.88.21:5001/" mode=http
```

## Troubleshooting

### Phone can't load the login page
- Check that MikroTik hotspot is serving the login.html file
- Verify the files were uploaded to `/hotspot/` folder
- Test by accessing any HTTP site - you should be redirected to login

### Voucher activation fails but login works
- The walled garden may not be configured correctly
- Check Flask server is running on the correct IP/port
- The login will still work because it falls back to direct MikroTik login

### "Invalid credentials" after entering voucher
- Make sure Flask created the hotspot user successfully
- Check MikroTik Users in IP → Hotspot → Users
- The voucher code should appear as both username and password

### How to check if files are being used
In MikroTik Terminal:
```
/ip hotspot print
# Look for "html-directory" - should show "hotspot" or "/hotspot"
```
