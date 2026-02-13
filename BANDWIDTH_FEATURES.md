# Bandwidth Control & Traffic Tracking Features

## Overview

The PisoNet Manager now includes comprehensive bandwidth control and traffic tracking features, allowing you to:

- **Track bandwidth usage** for each active user (upload/download)
- **Configure speed limits** per user or per voucher profile
- **Monitor real-time traffic** statistics
- **Apply dynamic bandwidth limits** via web admin or CLI

## Features Added

### 1. Traffic Tracking
- Monitor upload/download bytes for each active user
- View current transfer rates (bps)
- Track total data usage per session
- Real-time traffic statistics refresh

### 2. Bandwidth Control
- Set upload/download speed limits per user
- Apply predefined speed profiles (from profiles.json)
- Dynamic bandwidth adjustment for active users
- Remove bandwidth limits on-demand

### 3. Web Admin Interface
- New **Bandwidth Control** page at `/admin/bandwidth`
- View active users with traffic statistics
- Set/remove bandwidth limits with one click
- Speed presets based on voucher profiles
- Auto-refresh traffic stats every 10 seconds

### 4. CLI Commands
- New **Bandwidth Control** menu option (option 4)
- View users with traffic stats
- Set bandwidth limits interactively
- Remove bandwidth limits
- View all configured queues

## Setup Instructions

### 1. Run Database Migration

Before using the new features, run the migration script to add bandwidth columns to the database:

```powershell
cd d:\Github\mikrotik-project
.\env\Scripts\activate
python scripts\add_bandwidth_columns.py
```

This will add `rate_limit_up` and `rate_limit_down` columns to the vouchers table.

### 2. Configure Speed Profiles

Edit `profiles.json` to define your speed tiers:

```json
[
    {
        "name": "BASIC",
        "price": 5,
        "validity": "1h",
        "users": "1",
        "rate_up": "512K",
        "rate_down": "1M"
    },
    {
        "name": "STANDARD",
        "price": 10,
        "validity": "2h",
        "users": "1",
        "rate_up": "1M",
        "rate_down": "2M"
    },
    {
        "name": "PREMIUM",
        "price": 20,
        "validity": "5h",
        "users": "1",
        "rate_up": "5M",
        "rate_down": "10M"
    }
]
```

Speed formats:
- `K` = Kilobits (e.g., `512K` = 512 Kbps)
- `M` = Megabits (e.g., `2M` = 2 Mbps)

## Using the Features

### Web Admin Interface

1. **Access Bandwidth Control:**
   - Login to admin panel at `http://your-server:5000/admin`
   - Click **"Bandwidth Control"** in the sidebar menu

2. **View Traffic Statistics:**
   - See all active users with their:
     - MAC address
     - Download/Upload totals
     - Current speed limits
     - Real-time transfer rates

3. **Set Bandwidth Limit:**
   - Click **"Set Limit"** button for any user
   - Choose a preset or enter custom speeds
   - Click **"Apply"**

4. **Remove Bandwidth Limit:**
   - Click **"Remove"** button for any user
   - Confirm the action

### CLI Interface

1. **Start the CLI:**
   ```powershell
   python pisonet_manager_cli.py
   ```

2. **Navigate to Bandwidth Control:**
   - Select option `4` from main menu

3. **View Users with Traffic:**
   - Select option `1` - Shows all active users with traffic stats

4. **Set Bandwidth Limit:**
   - Select option `2`
   - Enter MAC address of user
   - Choose speed preset or enter custom values
   - Confirm to apply

5. **Remove Bandwidth Limit:**
   - Select option `3`
   - Enter MAC address
   - Confirm removal

6. **View All Queues:**
   - Select option `4` - Shows all configured bandwidth queues

## How It Works

### Automatic Application
When a user activates a voucher:
1. System checks voucher's `rate_limit_up` and `rate_limit_down` values
2. Creates MikroTik Simple Queue for the user's MAC address
3. Applies the configured speed limits
4. Queue remains active until session ends

### MikroTik Simple Queues
The system uses MikroTik's `/queue/simple` to enforce bandwidth limits:
- Each user gets a dedicated queue: `pisonet-{MAC-ADDRESS}`
- Queue tracks total bytes transferred
- Enforces max upload/download speeds
- Automatically removed when user disconnects

### Traffic Tracking
Traffic data is collected from:
1. **Hotspot Active Sessions** - Real-time connection data
2. **Simple Queues** - Detailed transfer statistics
3. Combined view in both web and CLI interfaces

## API Endpoints

For custom integrations:

### Get User Traffic
```
GET /admin/api/user-traffic
```

Response:
```json
{
    "success": true,
    "users": [
        {
            "user": "voucher-code",
            "mac": "AA:BB:CC:DD:EE:FF",
            "bytes_in_formatted": "15.2 MB",
            "bytes_out_formatted": "120.5 MB",
            "rate_in": "1024000",
            "rate_out": "2048000",
            "max_limit": "1M/2M"
        }
    ]
}
```

### Set Bandwidth Limit
```
POST /admin/api/set-bandwidth
Content-Type: application/json

{
    "mac": "AA:BB:CC:DD:EE:FF",
    "upload": "1M",
    "download": "2M"
}
```

### Remove Bandwidth Limit
```
POST /admin/api/remove-bandwidth
Content-Type: application/json

{
    "mac": "AA:BB:CC:DD:EE:FF"
}
```

## Troubleshooting

### Bandwidth limits not applied
1. Check MikroTik connection: CLI > Settings > Test Router Connection
2. Verify API credentials in `.env` file
3. Check MikroTik has `/queue/simple` enabled
4. Review server logs for errors

### Traffic stats showing zero
1. Ensure user activated voucher successfully
2. Check that Simple Queue was created on MikroTik
3. Verify queue name format: `pisonet-{MAC}`
4. Use MikroTik Winbox to verify queues: Queue > Simple Queues

### Migration errors
If migration script fails:
1. Backup your database: `cp instance/pisonet.db instance/pisonet.db.backup`
2. Try manual SQL:
   ```sql
   ALTER TABLE vouchers ADD COLUMN rate_limit_up VARCHAR(20) DEFAULT '1M';
   ALTER TABLE vouchers ADD COLUMN rate_limit_down VARCHAR(20) DEFAULT '2M';
   ```

## Notes

- **Existing vouchers**: Will have default limits (1M/2M) after migration
- **Developer codes**: Still work as unlimited duration, but bandwidth can be controlled
- **Profile changes**: Only affect newly generated vouchers
- **Queue persistence**: Queues are removed when users disconnect or session expires

## Support

For issues or questions:
1. Check logs in web admin dashboard
2. Use CLI test connection feature
3. Review MikroTik RouterOS logs
4. Ensure all dependencies are installed: `pip install -r requirements.txt`
