# MikroTik Pisonet Setup Guide

by Baronia and Verceles

***Latest Update: 23/01/2026***
- Added brief overview and guide about the system.

## Overview

This brief guide lists the basic hardware requirements and considerations for setting up a MikroTik-based pisonet (voucher/login) system.

## Hardware Needed

1. **Server PC** — Hosts the admin dashboard and the voucher/login services.  
2. **MikroTik router** — e.g., hAP lite or a more capable model depending on load.  
3. **Ethernet cables** — Test cables before use. At minimum two cables are required for a basic setup; three or more may be needed if additional routers are connected.  
4. **Second router (optional)** — Use for extended range or additional networks.

## Download

Download the latest configuration: [PUT LINK HERE]  
Download for MikroTik App configuration: [PUT LINK HERE]

## Setup Guide

1. Connect your ISP modem to the MikroTik's first Ethernet port (typically ether1).  
2. Connect the Server PC to the MikroTik's second Ethernet port (typically ether2).  
3. Download and install WinBox from the official MikroTik website: https://mikrotik.com/winbox.  
4. Connect the Server PC to the router with an Ethernet cable and open WinBox. Log in using the router's default credentials (see IMPORTANT below).  
5. In WinBox, open **Files**, drag the configuration file into the Files window, then select the file and click **Restore**. WinBox will lose connection during the restore—wait for it to reconnect.  
6. Update IP bindings, the walled-garden list, and static DNS entries to point to your Server PC's IP address.  
7. In the WinBox terminal, run a ping to 8.8.8.8 to verify internet connectivity.  
8. Launch the MikroTik Manager app, then start your server.  
9. After the server starts, verify you can access the admin dashboard.  
10. Users may now connect to the internet.

<h3 style="color: red;"><i>IMPORTANT!!!</i></h3>

Default credentials for this configuration (change immediately):  

***user: admin***  
***pass: 12345***

**Note:** If the configuration does not work, verify all hardware is functioning correctly before making further changes. 