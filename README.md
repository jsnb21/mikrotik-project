MIKROTIK PISONET SETUP GUIDE
----------------------------
*By Baronia and Verceles*

*Last Update:* 26/01/2026

Overview
--------
This guide covers the basic hardware and first steps required to set up a PisoNet hotspot using a MikroTik router and a server PC that hosts the voucher login and admin dashboard.

Hardware checklist
------------------
- Server PC — Runs the admin dashboard and voucher service.
- MikroTik router — A hAP lite or any newer MikroTik model is suitable.
- Ethernet cables — Use tested, working cables. At minimum you typically need two cables (server to router and WAN to router); add more if you connect extra devices.
- (Optional) Secondary router or access point — Use this for extended coverage if needed.

Downloads
---------
- Configuration files: add your configuration package link here.
- MikroTik Winbox: https://mikrotik.com/winbox

Quick start
-----------
1. Prepare the server PC and install the required software (see project `requirements.txt`).
2. Configure the MikroTik router using Winbox or the web interface. Apply the hotspot and walled-garden settings as required.
3. Place the project's `.env` file next to the application and update the MikroTik credentials and host settings.
4. Run the CLI manager:

```bash
python pisonet_manager_cli.py
```

Support
-------
For configuration examples and troubleshooting, refer to the project documentation or open an issue in the repository.

Replace any placeholders above (for example configuration links) with your actual resources before deploying.

Requirements
------------
- Python 3.8 or newer (3.11+ recommended).
- A virtual environment (recommended) and the packages listed in `requirements.txt`.

Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate   # Linux / macOS
.venv\Scripts\activate     # Windows (PowerShell)
pip install --upgrade pip
pip install -r requirements.txt
```

If you do not have `requirements.txt` up-to-date, generate it from your environment with:

```bash
pip freeze > requirements.txt
```

Additional documentation (placeholders)
-------------------------------------
Below are sections you can fill with project-specific instructions and examples.

Configuration
-------------
This project stores runtime settings in a `.env` file at the project root. Important variables:

- `MIKROTIK_HOST` — router IP or hostname (default: `192.168.88.1`).
- `MIKROTIK_PORT` — RouterOS API port (default: `8728`).
- `MIKROTIK_USERNAME` — API username (usually `admin`).
- `MIKROTIK_PASSWORD` — API password.
- `MIKROTIK_WAN_INTERFACE` — WAN interface name (e.g. `ether1`).
- `SERVER_IP` — IP address of the server hosting the web admin and voucher redirect.
- `AUTO_START_SERVER` — `true`/`false` to auto-start the Flask server on launch.

Example `.env` snippet:

```
MIKROTIK_HOST=192.168.88.1
MIKROTIK_PORT=8728
MIKROTIK_USERNAME=admin
MIKROTIK_PASSWORD=secret
MIKROTIK_WAN_INTERFACE=ether1
SERVER_IP=192.168.1.100
AUTO_START_SERVER=false
```

After editing `.env`, restart the CLI or use the Settings menu to re-apply values.

RouterOS Integration
---------------------
This project interacts with RouterOS using the RouterOS API to:

- Add/modify walled-garden (hotspot) entries that allow access to the admin and login pages.
- Manage IP bindings/address entries if you maintain static entries for the server.
- Add or update DNS static records that point human-friendly names to the `SERVER_IP`.

Notes and recommendations:
- Always keep a backup of the router configuration before running automated changes.  
- The CLI offers a `Test Router Connection` action to verify API connectivity before applying changes.  
- API operations are performed in a best-effort manner; inspect logs or test connectivity manually if changes fail.

Troubleshooting
---------------
Common issues and steps to resolve them:

- Router connection failures:
	- Verify IP/port/credentials in `.env`.  
	- Ensure the router API service is enabled and accessible from the server (firewall/NAT).  
	- Use Winbox to test connectivity and check RouterOS logs.

- Server not serving pages:
	- Check that the Flask server is running in the CLI (`Server Management -> View Server Status`).  
	- Confirm that `SERVER_IP` and firewall rules allow inbound connections to port 5000 if needed.


If in doubt, collect the output of `python pisonet_manager_cli.py` and open an issue with the output and steps to reproduce.

FAQ
---
Q: Where are vouchers stored?
A: Vouchers are stored in the SQLite database located at `instance/pisonet.db`.

Q: How do I revoke a user's access?
A: Use the `Hotspot Management` menu in the CLI and choose `Revoke User Access` or `Revoke All Users`.

Q: Can I run the web admin on a different port?
A: The Flask app uses port 5000 by default. To change it, modify the server startup logic or run behind a reverse proxy that listens on a different port.

Packaging and Deployment
------------------------
Suggested approaches for packaging:

- Windows: Use `pyinstaller` to create a single executable and optionally create an installer with Inno Setup.
	- Example: `pyinstaller --onefile pisonet_manager_cli.py`  
- Linux: Use `pyinstaller` or create a systemd service that launches the CLI on boot.

Remember to include the `instance` folder (database) and the `.env` file in your packaged artifact or document how to create them after installation.

Contributing
------------
Contributions are welcome. Suggested workflow:

1. Fork the repository and create a feature branch.  
2. Add tests or manual verification notes for CLI or RouterOS changes.  
3. Open a pull request with a clear description of the change and why it is needed.

Please keep commits focused and document any external changes required (router scripts, .env keys).

License
-------
Specify the project license here (for example, `MIT`). If you want me to add a license file, tell me which license to use and I will add a `LICENSE` file.

Contact / Support
-----------------
If you need help, open an issue in this repository. For commercial support or paid help, add contact details or an email address here.