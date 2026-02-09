# MIKROTIK PISONET SETUP GUIDE

**By Baronia and Verceles** *Last Update: 09/02/2026*

---

## Overview

This project provides an affordable, high-speed internet alternative for isolated areas using MikroTik hardware and a custom Python server. It functions as a prepaid voucher system, allowing users to access the web through budget-friendly micro-transactions and turning a single connection into a competitive, low-cost paid service.

---

## Hardware Checklist

Ensure you have the following components before beginning:

* **Server PC:** Runs the admin dashboard and voucher service.
* **MikroTik Router:** hAP lite or any newer model with RouterOS.
* **Ethernet Cables:** Minimum of two (Server-to-Router and WAN-to-Router).
* **Access Point (Optional):** Secondary router for extended Wi-Fi coverage.

---

## Quick Start

### 1. Software Prerequisites

* **Python:** 3.8 or newer (3.11+ recommended).
* **Winbox:** [Download MikroTik Winbox](https://mikrotik.com/winbox).
* **Config Files:** "repo"\backups\Mikrotik Config\Mikrotik Setup.backup.

### 2. Environment Setup

Clone the repository and set up your virtual environment:

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate      # Linux / macOS
.venv\Scripts\activate        # Windows (PowerShell)

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

```

### 3. Router Configuration

1. Connect to your MikroTik via **Winbox**.
2. Apply the provided configuration file.
3. Ensure **Hotspot** and **Walled-Garden** settings are active to allow communication with the Server PC.

---

## Configuration

The system uses a `.env` file for runtime settings. Create this file in the project root:

| Variable | Description | Default/Example |
| --- | --- | --- |
| `MIKROTIK_HOST` | Router IP address | `192.168.88.1` |
| `MIKROTIK_PORT` | RouterOS API port | `8728` |
| `MIKROTIK_USERNAME` | API username | `admin` |
| `MIKROTIK_PASSWORD` | API password | `secret` |
| `SERVER_IP` | IP of the Server PC | `192.168.1.100` |
| `AUTO_START_SERVER` | Start Flask on launch | `false` |

*Note: Change the default username and password for security purposes*

---

## Usage

### Running the Manager

Launch the CLI to manage vouchers and router settings:

```bash
python pisonet_manager_cli.py

```

### RouterOS Integration Features

The CLI communicates with your router to automate:

* **Walled Garden:** Automatically whitelist the admin/login pages.
* **DNS Management:** Create static records for user-friendly login URLs.
* **User Management:** Revoke or modify hotspot active users.

---

## Troubleshooting & FAQ

### Common Issues

* **Connection Failed:** Check if the API service is enabled in MikroTik (`IP > Services`). Ensure port `8728` isn't blocked by a firewall.
* **Pages Not Loading:** Verify the `SERVER_IP` in `.env` matches the PC's actual local IP and that port `5000` is open.

### FAQ

> **Q: Where are vouchers stored?** > A: They are kept in a local SQLite database at `instance/pisonet.db`.
> **Q: Can I change the Web Admin port?** > A: Yes, though it defaults to `5000`. You can modify the server startup script or use a reverse proxy.

---

## Deployment

To package the application for Windows:

```bash
pip install pyinstaller
pyinstaller --onefile pisonet_manager_cli.py

```

*Note: Ensure you bundle the `instance` folder and `.env` file with your executable.*

---

## Contributing & License

1. Fork the repo and create a feature branch.
2. Submit a PR with a clear description of changes.

---

**Support:** If you encounter bugs, please open an issue in the repository.
