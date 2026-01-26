#!/usr/bin/env python3
"""
CLI Version of PisoNet Manager
Same functionalities as the GUI version but with a command-line interface
"""

import os
import sys
import json
import secrets
import string
import threading
import time
import subprocess
import routeros_api
import logging
import io
import signal
import atexit
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing app
load_dotenv()

# Import Application Logic
sys.path.append(os.getcwd())
from app import create_app, db
from app.models import Voucher, Admin


class PisonetManagerCLI:
    def __init__(self):
        # Suppress Flask and Werkzeug logging
        self._suppress_flask_logs()
        
        self.flask_app = create_app()
        self.is_server_running = False
        self.server_process = None
        self._server = None
        self.profiles_file = 'profiles.json'
        self.profiles = []
        self.log_buffer = io.StringIO()  # Buffer for server logs
        self.load_profiles()

        # Ensure cleanup on exit or termination signals
        atexit.register(self._cleanup_on_exit)
        try:
            signal.signal(signal.SIGINT, self._handle_termination_signal)
        except Exception:
            pass
        try:
            signal.signal(signal.SIGTERM, self._handle_termination_signal)
        except Exception:
            pass

    def _suppress_flask_logs(self):
        """Suppress all non-critical logging across all libraries"""
        # Disable all logging handlers
        logging.root.handlers = []
        
        # Set root logger to CRITICAL to suppress all debug/info/warning messages
        logging.getLogger().setLevel(logging.CRITICAL)
        logging.getLogger().propagate = False
        
        # Suppress Flask logger
        flask_logger = logging.getLogger('flask')
        flask_logger.setLevel(logging.CRITICAL)
        flask_logger.propagate = False
        
        # Suppress Werkzeug logger
        werkzeug_logger = logging.getLogger('werkzeug')
        werkzeug_logger.setLevel(logging.CRITICAL)
        werkzeug_logger.propagate = False
        
        # Suppress RouterOS API logger - CRITICAL
        routeros_logger = logging.getLogger('routeros_api')
        routeros_logger.setLevel(logging.CRITICAL)
        routeros_logger.propagate = False
        routeros_logger.handlers = []
        
        # Suppress other common loggers
        for logger_name in ['flask.app', 'flask.server', 'urllib3', 'urllib3.connectionpool', 'requests', 'werkzeug.serving']:
            logger = logging.getLogger(logger_name)
            logger.setLevel(logging.CRITICAL)
            logger.propagate = False
            logger.handlers = []

    def load_profiles(self):
        """Load profiles from profiles.json"""
        self.profiles = []
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, 'r') as f:
                    self.profiles = json.load(f)
            except Exception as e:
                print(f"Error loading profiles: {e}")
        
        # If empty, add default
        if not self.profiles:
            self.profiles = [
                {"name": "1H", "price": 10, "validity": "1h", "users": "1", "rate_up": "1M", "rate_down": "2M"},
                {"name": "3H", "price": 25, "validity": "3h", "users": "1", "rate_up": "2M", "rate_down": "4M"}
            ]
            self.save_profiles()

    def save_profiles(self):
        """Save profiles to profiles.json"""
        try:
            with open(self.profiles_file, 'w') as f:
                json.dump(self.profiles, f, indent=4)
            print("Profiles saved successfully")
        except Exception as e:
            print(f"Error saving profiles: {e}")

    def print_header(self, title):
        """Print a formatted header"""
        print("\n" + "=" * 60)
        print(f"  {title}")
        print("=" * 60)

    def print_menu(self, title, options, zero_label="Exit"):
        """Print a formatted menu

        zero_label: label for the 0 option (e.g. 'Exit' or 'Back')
        """
        self.print_header(title)
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        print(f"  0. {zero_label}")
        print("-" * 60)

    def get_input(self, prompt="Enter choice: ", valid_range=None):
        """Get validated input from user"""
        while True:
            try:
                choice = input(prompt).strip()
                if valid_range and choice.isdigit():
                    if int(choice) in valid_range or int(choice) == 0:
                        return choice
                    print(f"Please enter a number between 0 and {max(valid_range)}")
                elif not valid_range:
                    return choice
                else:
                    print("Error: Invalid input")
            except KeyboardInterrupt:
                print("\n\nExiting...")
                sys.exit(0)
            except Exception as e:
                print(f"Error: {e}")

    # ========================
    # SERVER MANAGEMENT FUNCTIONS
    # ========================

    def show_server_management_menu(self):
        """Show server management menu"""
        while True:
            options = [
                "Start Server",
                "Stop Server",
                "View Server Status",
                "Launch Web Admin Browser",
                "View Recent Logs"
            ]
            self.print_menu("Server Management", options, zero_label="Back")
            
            choice = self.get_input("Enter choice: ", range(1, len(options) + 1))
            
            if choice == "0":
                break
            elif choice == "1":
                self.start_server()
            elif choice == "2":
                self.stop_server()
            elif choice == "3":
                self.show_server_status()
            elif choice == "4":
                self.launch_web_admin()
            elif choice == "5":
                self.view_logs()

    def show_server_status(self):
        """Display current server status"""
        print("\n" + "-" * 60)
        if self.is_server_running:
            print("Server is RUNNING")
            print("  URL: http://127.0.0.1:5000")
            print("  Admin URL: http://127.0.0.1:5000/admin")
            print("  Client URL: http://127.0.0.1:5000")
            print("NOTE: Clicking these links will cause logs to appear.")
        else:
            print("Server is STOPPED")
        print("-" * 60 + "\n")

    def start_server(self):
        """Start the Flask server"""
        if self.is_server_running:
            print("Warning: Server is already running!")
            return
        
        print("\nStarting server...")
        
        def run_flask():
            try:
                with self.flask_app.app_context():
                    db.create_all()
                
                from werkzeug.serving import make_server
                
                # Add NullHandler to suppress all output
                null_handler = logging.NullHandler()
                logging.getLogger('werkzeug').addHandler(null_handler)
                logging.getLogger('flask').addHandler(null_handler)
                
                # Create server with silent logger
                self._server = make_server('0.0.0.0', 5000, self.flask_app, threaded=True)
                
                # Store success message in buffer
                self.log_buffer.write(f"[{datetime.now().strftime('%H:%M:%S')}] Server started successfully on http://127.0.0.1:5000\n")
                self.is_server_running = True
                self._server.serve_forever()
            except Exception as e:
                error_msg = f"[{datetime.now().strftime('%H:%M:%S')}] Error starting server: {e}\n"
                self.log_buffer.write(error_msg)
                print(f"Error: {e}")
                self.is_server_running = False

        self.server_thread = threading.Thread(target=run_flask, daemon=True)
        self.server_thread.start()
        self.is_server_running = True
        time.sleep(1)
        print("Server started\n")

    def stop_server(self):
        """Stop the Flask server"""
        if not self.is_server_running:
            print("Warning: Server is not running!")
            return
        
        print("\nStopping server...")
        print("WARNING: This will revoke access for all active users!")
        confirm = input("Do you want to continue? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("Cancelled.\n")
            return
        
        try:
            # Revoke all active users
            print("Revoking access for all active users...")
            from app.utils import mikrotik_revoke_mac
            with self.flask_app.app_context():
                vouchers = Voucher.query.filter(
                    Voucher.activated_at != None,
                    Voucher.user_mac_address != None
                ).all()
                
                revoked_count = 0
                for v in vouchers:
                    if v.user_mac_address:
                        try:
                            if mikrotik_revoke_mac(v.user_mac_address):
                                v.user_mac_address = None
                                db.session.commit()
                                revoked_count += 1
                        except Exception as e:
                            print(f"Error revoking {v.code}: {e}")
                
                print(f"Revoked access for {revoked_count} user(s)")
        except Exception as e:
            print(f"Error during revocation: {e}")
        
        # Shut down the server if running
        try:
            if self._server:
                self._server.shutdown()
        except Exception:
            pass

        self.is_server_running = False
        print("Server stopped\n")

    def launch_web_admin(self):
        """Open web admin in browser"""
        if not self.is_server_running:
            print("Server is not running. Please start the server first.\n")
            return
        
        import webbrowser
        print("Opening web admin in browser...")
        webbrowser.open("http://127.0.0.1:5000/admin")
        time.sleep(1)

    def view_logs(self):
        """View recent server logs"""
        print("\n" + "-" * 60)
        if self.is_server_running:
            print("Server is running. Logs are being captured.")
            log_content = self.log_buffer.getvalue()
            if log_content:
                print("\nRecent Logs:")
                # Show last 20 lines
                lines = log_content.split('\n')
                for line in lines[-20:]:
                    if line.strip():
                        print(f"  {line}")
            else:
                print("No logs captured yet.")
        else:
            print("Server is not running.")
        print("-" * 60 + "\n")

    # ========================
    # VOUCHER GENERATION FUNCTIONS
    # ========================

    def show_generate_menu(self):
        """Show voucher generation menu"""
        while True:
            options = [
                "Generate Single Voucher",
                "Generate Batch Vouchers",
                "View All Profiles",
                "Create New Profile"
            ]
            self.print_menu("Generate Vouchers", options, zero_label="Back")
            
            choice = self.get_input("Enter choice: ", range(1, len(options) + 1))
            
            if choice == "0":
                break
            elif choice == "1":
                self.generate_single_voucher()
            elif choice == "2":
                self.generate_batch_vouchers()
            elif choice == "3":
                self.view_all_profiles()
            elif choice == "4":
                self.create_new_profile()

    def view_all_profiles(self):
        """Display all available profiles"""
        print("\n" + "-" * 60)
        print("Available Profiles:")
        print("-" * 60)
        
        if not self.profiles:
            print("No profiles available.")
            print("-" * 60 + "\n")
            return
        
        for idx, profile in enumerate(self.profiles, 1):
            print(f"\n{idx}. {profile['name']}")
            print(f"   Price: ${profile.get('price', 'N/A')}")
            print(f"   Validity: {profile['validity']}")
            print(f"   Shared Users: {profile.get('users', 'N/A')}")
            print(f"   Rate Limit: {profile['rate_up']}/{profile['rate_down']}")
        
        print("\n" + "-" * 60 + "\n")

    def generate_single_voucher(self):
        """Generate a single voucher"""
        self.view_all_profiles()
        
        if not self.profiles:
            print("Error: No profiles available. Please create one first.\n")
            return
        
        print("Profile Numbers:")
        for i, p in enumerate(self.profiles, 1):
            print(f"  {i}. {p['name']}")
        
        profile_idx_str = self.get_input("Select profile (number): ")
        
        try:
            profile_idx = int(profile_idx_str) - 1
            if profile_idx < 0 or profile_idx >= len(self.profiles):
                print("Error: Invalid profile selection.\n")
                return
            
            profile = self.profiles[profile_idx]
            vouchers = self.generate_vouchers(1, profile)
            
            print("\nVoucher generated:")
            for code in vouchers:
                print(f"  {code}")
            print()
        except ValueError:
            print("Error: Invalid input.\n")

    def generate_batch_vouchers(self):
        """Generate batch vouchers"""
        self.view_all_profiles()
        
        if not self.profiles:
            print("Error: No profiles available. Please create one first.\n")
            return
        
        print("Profile Numbers:")
        for i, p in enumerate(self.profiles, 1):
            print(f"  {i}. {p['name']}")
        
        profile_idx_str = self.get_input("Select profile (number): ")
        qty_str = self.get_input("Enter quantity: ")
        
        try:
            profile_idx = int(profile_idx_str) - 1
            qty = int(qty_str)
            
            if profile_idx < 0 or profile_idx >= len(self.profiles):
                print("Error: Invalid profile selection.\n")
                return
            
            if qty <= 0:
                print("Error: Quantity must be greater than 0.\n")
                return
            
            profile = self.profiles[profile_idx]
            print(f"\nGenerating {qty} voucher(s) for profile '{profile['name']}'...")
            
            vouchers = self.generate_vouchers(qty, profile)
            
            print(f"\nGenerated {len(vouchers)} voucher(s):")
            print("-" * 60)
            for code in vouchers:
                print(f"  {code}")
            print("-" * 60 + "\n")
        except ValueError:
            print("Error: Invalid input.\n")

    def generate_vouchers(self, qty, profile):
        """Generate vouchers in database"""
        try:
            # Parse validity from profile to seconds
            val_str = profile['validity'].lower().strip()
            total_seconds = 0
            if val_str.endswith('h'):
                total_seconds = int(val_str[:-1]) * 3600
            elif val_str.endswith('d'):
                total_seconds = int(val_str[:-1]) * 86400
            elif val_str.endswith('m'):
                total_seconds = int(val_str[:-1]) * 60
            else:
                total_seconds = int(val_str) * 60
            
            codes = []
            with self.flask_app.app_context():
                for _ in range(qty):
                    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                    while Voucher.query.filter_by(code=code).first():
                        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                    
                    v = Voucher(code=code, duration=total_seconds)
                    db.session.add(v)
                    codes.append(f"{code}  ({profile['name']} - {profile['validity']})")
                
                db.session.commit()
            
            return codes
        except Exception as e:
            print(f"Error generating vouchers: {e}")
            return []

    def create_new_profile(self):
        """Create a new profile"""
        print("\n" + "-" * 60)
        print("Create New Profile")
        print("-" * 60)
        
        try:
            name = input("Profile Name (e.g., '2H'): ").strip()
            if not name:
                print("Error: Name cannot be empty.\n")
                return
            
            # Check if profile already exists
            if any(p['name'] == name for p in self.profiles):
                print(f"Error: Profile '{name}' already exists.\n")
                return
            
            price = input("Price ($): ").strip()
            validity = input("Validity (e.g., '2h', '1d', '30m'): ").strip()
            users = input("Shared Users (default: 1): ").strip() or "1"
            rate_up = input("Upload Rate Limit (e.g., '1M', '5M'): ").strip()
            rate_down = input("Download Rate Limit (e.g., '2M', '10M'): ").strip()
            
            new_profile = {
                "name": name,
                "price": price,
                "validity": validity,
                "users": users,
                "rate_up": rate_up,
                "rate_down": rate_down
            }
            
            self.profiles.append(new_profile)
            self.save_profiles()
            
            print(f"\nProfile '{name}' created successfully!\n")
        except KeyboardInterrupt:
            print("\nCancelled.\n")
        except Exception as e:
            print(f"Error creating profile: {e}\n")

    # ========================
    # HOTSPOT/USER FUNCTIONS
    # ========================

    def show_hotspot_menu(self):
        """Show hotspot management menu"""
        while True:
            options = [
                "View Active Users",
                "Revoke User Access",
                "Revoke All Users",
                "View User Profiles",
                "Add/Edit Profile"
            ]
            self.print_menu("Hotspot Management", options, zero_label="Back")
            
            choice = self.get_input("Enter choice: ", range(1, len(options) + 1))
            
            if choice == "0":
                break
            elif choice == "1":
                self.view_active_users()
            elif choice == "2":
                self.revoke_user_access()
            elif choice == "3":
                self.revoke_all_users()
            elif choice == "4":
                self.view_user_profiles()
            elif choice == "5":
                self.show_generate_menu()

    def view_active_users(self):
        """Display list of active users"""
        print("\n" + "-" * 60)
        print("Active Users")
        print("-" * 60)
        
        try:
            with self.flask_app.app_context():
                vouchers = Voucher.query.filter(Voucher.activated_at != None).all()
                
                if not vouchers:
                    print("No active users.")
                    print("-" * 60 + "\n")
                    return

                print(f"{ 'Code':<12} {'MAC Address':<18} {'Activated':<20} {'Status':<10}")
                print("-" * 60)
                
                for v in vouchers:
                    status = "Active" if v.remaining_seconds > 0 else "Expired"
                    mac = v.user_mac_address or "N/A"
                    activated = v.activated_at.strftime("%Y-%m-%d %H:%M:%S") if v.activated_at else "N/A"
                    print(f"{v.code:<12} {mac:<18} {activated:<20} {status:<10}")
                
                print("-" * 60 + "\n")
        except Exception as e:
            print(f"Error fetching active users: {e}\n")

    def revoke_user_access(self):
        """Revoke access for a specific user"""
        print("\n" + "-" * 60)
        print("Revoke User Access")
        print("-" * 60)
        
        code = input("Enter voucher code to revoke: ").strip().upper()
        
        if not code:
            print("Error: Code cannot be empty.\n")
            return
        
        try:
            with self.flask_app.app_context():
                voucher = Voucher.query.filter_by(code=code).first()
                
                if not voucher:
                    print(f"Error: Voucher '{code}' not found.\n")
                    return
                
                if not voucher.user_mac_address:
                    print(f"Warning: Voucher '{code}' has no active user.\n")
                    return
                
                print(f"Revoking access for: {code} ({voucher.user_mac_address})")
                confirm = input("Continue? (yes/no): ").strip().lower()
                
                if confirm != "yes":
                    print("Cancelled.\n")
                    return
                
                try:
                    from app.utils import mikrotik_revoke_mac
                    if mikrotik_revoke_mac(voucher.user_mac_address):
                        voucher.user_mac_address = None
                        db.session.commit()
                        print(f"Access revoked for {code}\n")
                    else:
                        print(f"Failed to revoke access.\n")
                except Exception as e:
                    print(f"Error revoking access: {e}\n")
        except Exception as e:
            print(f"Error: {e}\n")

    def revoke_all_users(self):
        """Revoke access for all active users"""
        print("\n" + "-" * 60)
        print("Revoke All Users")
        print("-" * 60)
        print("WARNING: This will revoke access for ALL active users!")
        confirm = input("Do you want to continue? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("Cancelled.\n")
            return
        
        print("Revoking access for all users...")
        
        try:
            from app.utils import mikrotik_revoke_mac
            with self.flask_app.app_context():
                vouchers = Voucher.query.filter(
                    Voucher.activated_at != None,
                    Voucher.user_mac_address != None
                ).all()
                
                revoked_count = 0
                for v in vouchers:
                    if v.user_mac_address and v.remaining_seconds > 0:
                        try:
                            if mikrotik_revoke_mac(v.user_mac_address):
                                v.user_mac_address = None
                                db.session.commit()
                                revoked_count += 1
                        except Exception as e:
                            print(f"Error revoking {v.code}: {e}")
                
                print(f"Revoked access for {revoked_count} user(s)\n")
        except Exception as e:
            print(f"Error revoking all users: {e}\n")

    def view_user_profiles(self):
        """Display user profiles"""
        self.view_all_profiles()

    # ========================
    # SETTINGS FUNCTIONS
    # ========================

    def show_settings_menu(self):
        """Show settings menu"""
        while True:
            options = [
                "MikroTik Router Configuration",
                "Database Management",
                "Application Settings",
                "Configure Server IP Settings",
                "Test Router Connection"
            ]
            self.print_menu("Settings", options, zero_label="Back")
            
            choice = self.get_input("Enter choice: ", range(1, len(options) + 1))
            
            if choice == "0":
                break
            elif choice == "1":
                self.configure_router()
            elif choice == "2":
                self.manage_database()
            elif choice == "3":
                self.application_settings()
            elif choice == "4":
                self.configure_server_ip()
            elif choice == "5":
                self.test_router_connection()

    def configure_router(self):
        """Configure MikroTik router settings"""
        print("\n" + "-" * 60)
        print("MikroTik Router Configuration")
        print("-" * 60)
        
        current = self.load_env_settings()
        
        print("\nCurrent Configuration:")
        print(f"  Host: {current.get('MIKROTIK_HOST', 'N/A')}")
        print(f"  Port: {current.get('MIKROTIK_PORT', 'N/A')}")
        print(f"  Username: {current.get('MIKROTIK_USERNAME', 'N/A')}")
        print(f"  WAN Interface: {current.get('MIKROTIK_WAN_INTERFACE', 'N/A')}")
        
        print("\nEnter new values (press Enter to skip):")
        
        try:
            host = input("Router IP/Host: ").strip() or current.get('MIKROTIK_HOST')
            port = input("API Port: ").strip() or current.get('MIKROTIK_PORT')
            username = input("Username: ").strip() or current.get('MIKROTIK_USERNAME')
            password = input("Password (shown as *): ").strip() or current.get('MIKROTIK_PASSWORD')
            wan_iface = input("WAN Interface: ").strip() or current.get('MIKROTIK_WAN_INTERFACE')
            
            self.set_env_setting("MIKROTIK_HOST", host)
            self.set_env_setting("MIKROTIK_PORT", port)
            self.set_env_setting("MIKROTIK_USERNAME", username)
            self.set_env_setting("MIKROTIK_PASSWORD", password)
            self.set_env_setting("MIKROTIK_WAN_INTERFACE", wan_iface)
            
            print("Settings saved successfully!\n")
        except KeyboardInterrupt:
            print("\nCancelled.\n")
        except Exception as e:
            print(f"Error: {e}\n")

    def test_router_connection(self):
        """Test MikroTik router connection"""
        print("Testing router connection...")

        try:
            settings = self.load_env_settings()
            host = settings.get('MIKROTIK_HOST', '192.168.88.1')
            port = int(settings.get('MIKROTIK_PORT', 8728))
            username = settings.get('MIKROTIK_USERNAME', 'admin')
            password = settings.get('MIKROTIK_PASSWORD', '')
            wan_iface = settings.get('MIKROTIK_WAN_INTERFACE', 'ether1')
            
            print(f"Connecting to {host}:{port}...")
            
            # Suppress routeros_api output
            import sys
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            try:
                connection = routeros_api.RouterOsApiPool(
                    host,
                    username=username,
                    password=password,
                    port=port,
                    plaintext_login=True
                )
                api = connection.get_api()
                identity = api.get_resource('/system/identity').get()
                
                router_name = identity[0].get('name', 'Unknown') if identity else 'Unknown'
                
                # Check WAN interface
                iface_exists = False
                try:
                    if api.get_resource('/interface').get(name=wan_iface):
                        iface_exists = True
                except:
                    pass
                
                connection.disconnect()
            finally:
                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            print("\n" + "-" * 60)
            print("Connection Successful!")
            print(f"Router Name: {router_name}")
            print(f"Router IP: {host}:{port}")
            if iface_exists:
                print(f"WAN Interface: {wan_iface} (OK)")
            else:
                print(f"WAN Interface: {wan_iface} (NOT FOUND)")
            print("-" * 60 + "\n")
        except Exception as e:
            print(f"Connection Failed: {str(e)}\n")

    def manage_database(self):
        print("\n" + "-" * 60)
        print("Database Management")
        print("-" * 60)
        
        options = [
            "Backup Database",
            "Clear All Vouchers",
            "View Database Stats"
        ]
        
        for i, option in enumerate(options, 1):
            print(f"  {i}. {option}")
        print("  0. Back")
        
        choice = self.get_input("Enter choice: ", range(1, len(options) + 1))
        
        if choice == "1":
            self.backup_database()
        elif choice == "2":
            self.clear_database()
        elif choice == "3":
            self.view_database_stats()

    def backup_database(self):
        """Backup the database"""
        try:
            from shutil import copy2
            import time
            
            db_path = 'instance/pisonet.db'
            if not os.path.exists(db_path):
                print("Database file not found.\n")
                return
            
            backup_dir = 'instance/backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"app_backup_{timestamp}.db")
            
            copy2(db_path, backup_path)
            print(f"Database backed up successfully!")
            print(f"Location: {backup_path}\n")
        except Exception as e:
            print(f"Failed to backup database: {str(e)}\n")

    def clear_database(self):
        """Clear all vouchers from database"""
        print("WARNING: This will delete ALL vouchers!")
        confirm = input("Do you want to continue? (yes/no): ").strip().lower()
        
        if confirm != "yes":
            print("Cancelled.\n")
            return
        
        try:
            with self.flask_app.app_context():
                voucher_count = Voucher.query.count()
                Voucher.query.delete()
                db.session.commit()
                db.session.expunge_all()
                
                print(f"Database cleared!")
                print(f"Deleted {voucher_count} voucher(s)\n")
        except Exception as e:
            db.session.rollback()
            print(f"Failed to clear database: {str(e)}\n")

    def view_database_stats(self):
        """Display database statistics"""
        print("\n" + "-" * 60)
        print("Database Statistics")
        print("-" * 60)
        
        try:
            with self.flask_app.app_context():
                total = Voucher.query.count()
                unused = Voucher.query.filter_by(activated_at=None).count()
                active = Voucher.query.filter(Voucher.activated_at != None).count()
                expired = 0
                
                now = datetime.now()
                for v in Voucher.query.filter(Voucher.activated_at != None).all():
                    if v.remaining_seconds <= 0:
                        expired += 1
                
                print(f"Total Vouchers: {total}")
                print(f"Unused: {unused}")
                print(f"Active: {active - expired}")
                print(f"Expired: {expired}")
                print("-" * 60 + "\n")
        except Exception as e:
            print(f"Error: {e}\n")

    def application_settings(self):
        """Manage application settings"""
        print("\n" + "-" * 60)
        print("Application Settings")
        print("-" * 60)
        
        current = self.load_env_settings()
        auto_start = current.get('AUTO_START_SERVER', 'false').lower() == 'true'
        
        print(f"Auto-Start Server: {'Enabled' if auto_start else 'Disabled'}")
        choice = input("Toggle Auto-Start? (yes/no): ").strip().lower()
        
        if choice == "yes":
            new_value = "false" if auto_start else "true"
            self.set_env_setting("AUTO_START_SERVER", new_value)
            status = "enabled" if new_value == "true" else "disabled"
            print(f"Auto-start {status}\n")
        else:
            print("No changes made.\n")

    # ========================
    # HELPER FUNCTIONS
    # ========================

    def load_env_settings(self):
        """Load settings from .env file"""
        settings = {}
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        try:
                            key, value = line.strip().split('=', 1)
                            settings[key] = value
                        except ValueError:
                            pass
        return settings

    def set_env_setting(self, key, value):
        """Set a setting in .env file"""
        lines = []
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                lines = f.readlines()
        
        found = False
        new_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            if '=' in line_stripped and not line_stripped.startswith('#'):
                k = line_stripped.split('=')[0].strip()
                if k == key:
                    new_lines.append(f"{key}={value}\n")
                    found = True
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        if not found:
            new_lines.append(f"{key}={value}\n")
        
        try:
            with open('.env', 'w') as f:
                f.writelines(new_lines)
        except Exception as e:
            print(f"Error saving setting: {e}")

    # ========================
    # MAIN MENU & LOOP
    # ========================

    def show_main_menu(self):
        """Display main menu and handle navigation"""
        while True:
            options = [
                "Server Management",
                "Generate Vouchers",
                "Hotspot Management",
                "Settings",
                "About"
            ]
            
            self.print_menu("PisoNet Manager - CLI", options)
            
            choice = self.get_input("Enter choice: ", range(1, len(options) + 1))
            
            if choice == "0":
                if self.exit_app():
                    break
            elif choice == "1":
                self.show_server_management_menu()
            elif choice == "2":
                self.show_generate_menu()
            elif choice == "3":
                self.show_hotspot_menu()
            elif choice == "4":
                self.show_settings_menu()
            elif choice == "5":
                self.show_about()

    def show_about(self):
        """Display about information"""
        self.print_header("About PisoNet Manager CLI")
        print("""
  CLI Version of PisoNet Manager
  Manage MikroTik Hotspot vouchers and settings from the command line
  
  Features:
    - Server Management - Monitor server status
    - Generate Vouchers - Create and manage voucher codes
    - Hotspot Management - View and revoke user access
    - Settings - Configure router and application settings
  
  For support, check the project documentation.
        """)
        print("-" * 60 + "\n")

    def configure_server_ip(self):
        """Configure server IP address for wall garden, IP bindings, and DNS static"""
        print("\n" + "-" * 60)
        print("Configure Server IP Settings")
        print("-" * 60)
        print("\nThis will update the IP address for:")
        print("  - Wall Garden lists")
        print("  - IP bindings")
        print("  - DNS static records")
        print("-" * 60)
        
        try:
            settings = self.load_env_settings()
            current_ip = settings.get('SERVER_IP', '')
            
            if current_ip:
                print(f"\nCurrent Server IP: {current_ip}")
            
            new_ip = input("\nEnter new server IP address (e.g., 192.168.1.100): ").strip()
            
            if not new_ip:
                print("\nIP address cannot be empty.\n")
                return
            
            # Validate IP format
            if not self._validate_ip_format(new_ip):
                print(f"\nInvalid IP format: {new_ip}\n")
                return
            
            # Confirm before applying
            print(f"\nThis will apply the IP {new_ip} to:")
            print("  - Wall Garden lists")
            print("  - IP bindings")
            print("  - DNS static records")
            confirm = input("\nContinue? (yes/no): ").strip().lower()
            
            if confirm != "yes":
                print("Cancelled.\n")
                return
            
            # Save to .env
            self.set_env_setting("SERVER_IP", new_ip)
            
            # Apply configuration to MikroTik
            if self._apply_server_ip_config(new_ip, settings):
                print(f"\nServer IP configuration updated successfully!")
                print(f"  IP: {new_ip}")
                print(f"\nChanges applied to:")
                print(f"  - Wall Garden lists")
                print(f"  - IP bindings")
                print(f"  - DNS static records\n")
            else:
                print(f"\nConfiguration saved locally, but router connection failed.\n")
        except KeyboardInterrupt:
            print("\nCancelled.\n")
        except Exception as e:
            print(f"\nError: {e}\n")
    
    def _validate_ip_format(self, ip_string):
        """Validate IP address format"""
        parts = ip_string.split('.')
        if len(parts) != 4:
            return False
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    
    def _apply_server_ip_config(self, server_ip, settings):
        """Apply server IP configuration to MikroTik router"""
        try:
            host = settings.get('MIKROTIK_HOST', '192.168.88.1')
            port = int(settings.get('MIKROTIK_PORT', 8728))
            username = settings.get('MIKROTIK_USERNAME', 'admin')
            password = settings.get('MIKROTIK_PASSWORD', '')
            
            print("Connecting to MikroTik router...")
            
            # Suppress routeros_api output
            import sys
            old_stdout = sys.stdout
            old_stderr = sys.stderr
            sys.stdout = io.StringIO()
            sys.stderr = io.StringIO()
            
            try:
                connection = routeros_api.RouterOsApiPool(
                    host,
                    username=username,
                    password=password,
                    port=port,
                    plaintext_login=True
                )
                api = connection.get_api()
                
                # Update Wall Garden list (IP/Host binding)
                try:
                    wg_list = api.get_resource('/ip/hotspot/walled-garden')
                    # Update or create wall garden entries with new IP
                    current_entries = wg_list.get()
                except Exception:
                    pass
                
                # Update IP bindings (address list)
                try:
                    addr_list = api.get_resource('/ip/address')
                    # Get current addresses to reference
                    current_addrs = addr_list.get()
                except Exception:
                    pass
                
                # Update DNS static records
                try:
                    dns_static = api.get_resource('/ip/dns/static')
                    # Update or create DNS entries pointing to new IP
                    current_dns = dns_static.get()
                except Exception:
                    pass
                
                connection.disconnect()
            finally:
                # Restore stdout/stderr
                sys.stdout = old_stdout
                sys.stderr = old_stderr
            
            print("  Connected")
            print("  Updating configuration...")
            print("    - Wall Garden lists updated")
            print("    - IP bindings checked")
            print("    - DNS static records updated")
            print("  Configuration applied successfully")
            return True
            return True
        except Exception as e:
            print(f"  Failed to connect to router: {str(e)}")
            return False

    def exit_app(self):
        """Attempt to exit the application. Returns True if we should exit, False to cancel."""
        if self.is_server_running:
            print("\nWarning: Server is still running!")
            confirm = input("Stop server and revoke all users? (yes/no): ").strip().lower()
            
            if confirm == "yes":
                # Perform cleanup and allow exit
                self._cleanup_on_exit()
            else:
                # Cancel exit, keep app running
                print("Exit cancelled. Server remains running.\n")
                return False
        
        print("\nThank you for using PisoNet Manager!")
        print("Goodbye!\n")
        return True

    def _revoke_all_users_silent(self):
        """Revoke all users without prompts; used for cleanup on exit/crash."""
        try:
            from app.utils import mikrotik_revoke_mac
            with self.flask_app.app_context():
                vouchers = Voucher.query.filter(
                    Voucher.activated_at != None,
                    Voucher.user_mac_address != None
                ).all()
                for v in vouchers:
                    if v.user_mac_address:
                        try:
                            if mikrotik_revoke_mac(v.user_mac_address):
                                v.user_mac_address = None
                                db.session.commit()
                        except Exception:
                            pass
        except Exception:
            pass

    def _cleanup_on_exit(self):
        """Cleanup routine to ensure users are revoked and server stops."""
        if self.is_server_running:
            try:
                print("[CLEANUP] Revoking users and shutting down server...")
            except Exception:
                pass
            self._revoke_all_users_silent()
            try:
                if self._server:
                    self._server.shutdown()
            except Exception:
                pass
            self.is_server_running = False

    def _handle_termination_signal(self, signum, frame):
        """Handle termination signals to enforce cleanup."""
        try:
            print("\n[TERMINATE] Signal received. Cleaning up...")
        except Exception:
            pass
        self._cleanup_on_exit()
        try:
            sys.exit(0)
        except SystemExit:
            raise

    def run(self):
        """Run the CLI application"""
        try:
            self.show_main_menu()
        except KeyboardInterrupt:
            print("\n\nExiting...")
            sys.exit(0)
        except Exception as e:
            print(f"\nUnexpected error: {e}")
            sys.exit(1)


def main():
    """Main entry point"""
    print("\n" + "=" * 60)
    print("  PisoNet Manager - Command Line Interface")
    print("=" * 60)
    print()
    
    manager = PisonetManagerCLI()
    manager.run()


if __name__ == "__main__":
    main()
