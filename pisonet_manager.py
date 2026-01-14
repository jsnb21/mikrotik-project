import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import customtkinter as ctk
import threading
import webbrowser
import sys
import os
import json
import secrets
import string
import ctypes
import queue
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing app
load_dotenv()

# Enable High DPI Support (Windows)
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

# Import Application Logic
sys.path.append(os.getcwd())
from app import create_app, db
from app.models import Voucher, Admin

class IORedirector(object):
    def __init__(self, queue, original_stream):
        self.queue = queue
        self.original_stream = original_stream

    def write(self, str):
        self.queue.put(str)
        self.original_stream.write(str)

    def flush(self):
        self.original_stream.flush()

class CustomMessageBox(ctk.CTkToplevel):
    def __init__(self, title, message, type="info"):
        super().__init__()
        self.title(title)
        
        # Dimensions and Centering
        width = 420
        height = 220
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = int((screen_width/2) - (width/2))
        y = int((screen_height/2) - (height/2))
        self.geometry(f'{width}x{height}+{x}+{y}')
        
        self.resizable(False, False)
        self.attributes("-topmost", True)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # Style based on type
        if type == "error":
            icon_char = "✕"
            icon_color = "#ff5f52" # Coral Red
        elif type == "success" or title.lower() == "success":
            icon_char = "✓"
            icon_color = "#ffd41d" # Vibrant Yellow
        else:
            icon_char = "ℹ"
            icon_color = "#4b7178" # Muted Blue-Grey

        # Icon
        self.lbl_icon = ctk.CTkLabel(self, text=icon_char, font=("Arial", 48), text_color=icon_color)
        self.lbl_icon.pack(pady=(20, 5))

        # Message
        self.lbl_msg = ctk.CTkLabel(self, text=message, font=("Arial", 14), wraplength=380, text_color=("black", "white"))
        self.lbl_msg.pack(pady=10, padx=20)

        # OK Button
        self.btn_ok = ctk.CTkButton(self, text="OK", command=self.destroy, width=100, fg_color="#ffd41d", hover_color="#e6c019", text_color="black", font=("Arial", 14, "bold"))
        self.btn_ok.pack(pady=(0, 20))
        
        self.grab_set()
        self.focus_force()

class ToolTip(object):
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tip_window = None
        self.widget.bind("<Enter>", self.show_tip)
        self.widget.bind("<Leave>", self.hide_tip)

    def show_tip(self, event=None):
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(self.tip_window, text=self.text, justify=tk.LEFT,
                       background="#333333", foreground="white",
                       relief=tk.SOLID, borderwidth=0, font=("Arial", 10))
        label.pack(ipadx=5, ipady=2)

    def hide_tip(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None

class PisonetManager(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Set theme
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")

        self.title("MikroTik Hotspot Manager")
        self.geometry("1000x650")
        self.resizable(False, False)
        try:
            self.iconbitmap("app/static/img/favicon.ico")
        except:
            pass

        # App State
        self.flask_app = create_app()
        self.flask_thread = None
        self.server = None
        self.is_server_running = False
        self.profiles_file = 'profiles.json'
        
        # Configure Colors
        self.sidebar_color = "#0b343d"
        
        # Logging Setup
        self.setup_logging()

        # Initialize UI
        self.setup_ui()
        self.load_profiles()
        
        # Start logging loop
        self.update_log_display()

    def setup_logging(self):
        self.log_queue = queue.Queue()
        sys.stdout = IORedirector(self.log_queue, sys.stdout)
        sys.stderr = IORedirector(self.log_queue, sys.stderr)

    def update_log_display(self):
        while not self.log_queue.empty():
            try:
                msg = self.log_queue.get_nowait()
                if "DashboardView" in self.frames:
                    self.frames["DashboardView"].log_area.configure(state="normal")
                    self.frames["DashboardView"].log_area.insert("end", msg)
                    self.frames["DashboardView"].log_area.see("end")
                    self.frames["DashboardView"].log_area.configure(state="disabled")
            except:
                pass
        self.after(100, self.update_log_display)

    def setup_ui(self):
        # Split Layout: Left Sidebar, Right Content
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Store navigation buttons
        self.nav_buttons = {}

        # 1. Sidebar
        self.sidebar_frame = ctk.CTkFrame(self, fg_color=self.sidebar_color, width=200, corner_radius=0)
        self.sidebar_frame.grid(row=0, column=0, sticky="ns")
        self.sidebar_frame.grid_propagate(False)

        # Sidebar Header
        lbl_brand = ctk.CTkLabel(self.sidebar_frame, text="Admin", font=("Helvetica", 20, "bold"), text_color="white")
        lbl_brand.pack(pady=30)
        
        # Sidebar Menu Buttons
        self.create_sidebar_btn("Dashboard", self.show_dashboard)
        self.create_sidebar_btn("Generate", self.show_generate)
        self.create_sidebar_btn("Hotspot", self.show_hotspot)
        self.create_sidebar_btn("Settings", self.show_settings)

        # 3. Content Area
        self.content_area = ctk.CTkFrame(self, fg_color="transparent")
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.content_area.grid_columnconfigure(0, weight=1)
        self.content_area.grid_rowconfigure(0, weight=1)

        # 2. Status Bar (Bottom)
        self.grid_rowconfigure(1, weight=0) # Status bar row

        self.status_bar = ctk.CTkFrame(self, height=30, corner_radius=0, fg_color=("#E0E0E0", "#2b2b2b"))
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        self.status_indicator = ctk.CTkLabel(self.status_bar, text="●", text_color=("black", "gray"), font=("Arial", 16))
        self.status_indicator.pack(side=tk.LEFT, padx=(10, 5), pady=2)
        
        self.status_label = ctk.CTkLabel(self.status_bar, text="Server Stopped", font=("Arial", 12))
        self.status_label.pack(side=tk.LEFT)

        self.spinner_label = ctk.CTkLabel(self.status_bar, text="", font=("Courier New", 14, "bold"))
        self.spinner_label.pack(side=tk.LEFT, padx=5)

        self.notification_label = ctk.CTkLabel(self.status_bar, text="", font=("Arial", 12), text_color="#ffd41d")
        self.notification_label.pack(side=tk.RIGHT, padx=20)
        
        # Define Frames for each view
        self.frames = {}
        for F in (DashboardView, GenerateView, HotspotView, SettingsView):
            frame = F(parent=self.content_area, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Show initial view
        self.show_dashboard()

    def create_sidebar_btn(self, text, command):
        icon_map = {
            "Dashboard": "🏠",
            "Generate": "🎫",
            "Hotspot": "📡",
            "Settings": "⚙"
        }
        icon = icon_map.get(text, "●")
        
        # Container Frame (Simulates Button)
        btn_frame = ctk.CTkFrame(self.sidebar_frame, fg_color="transparent", height=40, corner_radius=6)
        btn_frame.pack(fill=tk.X, pady=2, padx=10)
        btn_frame.pack_propagate(False)

        # Event Handlers
        def on_click(e): command()
        
        def on_enter(e):
            if getattr(self, "active_btn_name", "") != text:
                btn_frame.configure(fg_color="#2E3B55")

        def on_leave(e):
            if getattr(self, "active_btn_name", "") != text:
                btn_frame.configure(fg_color="transparent")

        # Icon Label (Normal Font)
        icon_lbl = ctk.CTkLabel(btn_frame, text=icon, font=("Arial", 20), width=40)
        icon_lbl.pack(side=tk.LEFT, padx=(5, 0))
        
        # Text Label (Bold Font)
        text_lbl = ctk.CTkLabel(btn_frame, text=text, font=("Arial", 14, "bold"), anchor="w")
        text_lbl.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Bind events
        for w in (btn_frame, icon_lbl, text_lbl):
            w.bind("<Button-1>", on_click)
            w.bind("<Enter>", on_enter)
            w.bind("<Leave>", on_leave)

        self.nav_buttons[text] = btn_frame

    def show_dashboard(self): self.show_frame("DashboardView")
    def show_generate(self): self.show_frame("GenerateView")
    def show_hotspot(self): self.show_frame("HotspotView")
    def show_settings(self): self.show_frame("SettingsView")

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        
        # Highlight active button
        active_btn_name = page_name.replace("View", "")
        self.active_btn_name = active_btn_name
        for name, btn in self.nav_buttons.items():
            if name == active_btn_name:
                btn.configure(fg_color="#4a5a7d") # Active color
            else:
                btn.configure(fg_color="transparent") # Default color

        # Refresh if needed
        if hasattr(frame, 'refresh'):
            frame.refresh()

    def start_loading_animation(self):
        self._is_loading = True
        self._animate_spinner()

    def stop_loading_animation(self):
        self._is_loading = False
        self.spinner_label.configure(text="")

    def show_notification(self, text, duration=2000):
        self.notification_label.configure(text=text)
        self.after(duration, lambda: self.notification_label.configure(text=""))

    def _animate_spinner(self):
        if not self._is_loading: return
        chars = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
        if not hasattr(self, '_spinner_idx'): self._spinner_idx = 0
        self.spinner_label.configure(text=chars[self._spinner_idx])
        self._spinner_idx = (self._spinner_idx + 1) % len(chars)
        self.after(80, self._animate_spinner)

    def draw_status_indicator(self, color):
        self.status_indicator.configure(text_color=color)

    def load_profiles(self):
        self.profiles = []
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, 'r') as f:
                    self.profiles = json.load(f)
            except: pass
        
        # If empty, add default
        if not self.profiles:
            self.profiles = [
                {"name": "1H", "price": 10, "validity": "1h", "users": "1", "rate_up": "1M", "rate_down": "2M"},
                {"name": "3H", "price": 25, "validity": "3h", "users": "1", "rate_up": "2M", "rate_down": "4M"}
            ]
            self.save_profiles()

    def save_profiles(self):
        try:
            with open(self.profiles_file, 'w') as f:
                json.dump(self.profiles, f, indent=4)
        except Exception as e:
            print(f"Error saving profiles: {e}")


    def start_server(self):
        if self.is_server_running:
            self.stop_server()
            return

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting server...")

        def run_flask():
            with self.flask_app.app_context(): db.create_all()
            from werkzeug.serving import make_server
            self.server = make_server('0.0.0.0', 5000, self.flask_app)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Server started successfully on http://0.0.0.0:5000")
            self.server.serve_forever()

        self.flask_thread = threading.Thread(target=run_flask, daemon=True)
        self.flask_thread.start()
        self.is_server_running = True
        self.draw_status_indicator("#00FF00")
        self.status_label.configure(text="Server Running: http://127.0.0.1:5000")
        
        # Update dashboard button state
        self.frames["DashboardView"].btn_start.configure(state="disabled", text="Running...")
        self.frames["DashboardView"].btn_stop.configure(state="normal")
        
        self.after(2000, lambda: webbrowser.open("http://127.0.0.1:5000/admin"))

    def stop_server(self):
        if not self.is_server_running: return
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Stopping server...")
        if self.server:
            self.server.shutdown()
            
        self.is_server_running = False
        self.flask_thread = None
        self.server = None
        self.draw_status_indicator(("black", "gray"))
        self.status_label.configure(text="Server Stopped")
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Server stopped.")
        
        # Update dashboard button state
        self.frames["DashboardView"].btn_start.configure(state="normal", text="Start Server")
        self.frames["DashboardView"].btn_stop.configure(state="disabled")


class DashboardView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent, fg_color="transparent")
        self.controller = controller
        
        lb = ctk.CTkLabel(self, text="System Dashboard", font=("Helvetica", 24, "bold"))
        lb.pack(anchor="w", pady=(0, 20))

        # Controls
        control_frame = ctk.CTkFrame(self, border_width=2, border_color="#E0E0E0")
        control_frame.pack(fill=tk.X, padx=2)
        
        # Label inside frame - simulated by label on top padding or just a label inside
        ctk.CTkLabel(control_frame, text="Services", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        btns_frame = ctk.CTkFrame(control_frame, fg_color="transparent")
        btns_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        self.btn_start = ctk.CTkButton(btns_frame, text="Start Server", command=controller.start_server, fg_color="#ffd41d", hover_color="#e6c019", text_color="black", text_color_disabled="#3d3300", font=("Arial", 12, "bold"))
        self.btn_start.pack(side=tk.LEFT, padx=5)

        self.btn_stop = ctk.CTkButton(btns_frame, text="Stop Server", command=controller.stop_server, state="disabled", fg_color="#ff5f52", hover_color="#e65549", text_color="white", text_color_disabled="#dcdcdc", font=("Arial", 12, "bold"))
        self.btn_stop.pack(side=tk.LEFT, padx=5)

        ctk.CTkButton(btns_frame, text="Launch Web Admin", command=self.launch_admin, fg_color="#4b7178", hover_color="#3a585e", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)

        self.btn_copy = ctk.CTkButton(btns_frame, text="📋", width=40, command=self.copy_link, fg_color="#4b7178", hover_color="#3a585e", font=("Arial", 16))
        self.btn_copy.pack(side=tk.LEFT, padx=5)
        ToolTip(self.btn_copy, "Copy Link to Clipboard")

        # Logs
        log_label_frame = ctk.CTkFrame(self, border_width=2, border_color="#E0E0E0")
        log_label_frame.pack(fill=tk.BOTH, expand=True, pady=20, padx=2)
        
        ctk.CTkLabel(log_label_frame, text="Logs", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        # Using CTkTextbox instead of ScrolledText
        self.log_area = ctk.CTkTextbox(log_label_frame, height=200)
        self.log_area.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.log_area.insert("0.0", "Ready...\n")
        self.log_area.configure(state="disabled")

    def copy_link(self):
        self.controller.clipboard_clear()
        self.controller.clipboard_append("http://127.0.0.1:5000/admin")
        self.controller.update() # Required to finalize clipboard
        self.controller.show_notification("Link has been copied!")

    def launch_admin(self):
        if self.controller.is_server_running:
            webbrowser.open("http://127.0.0.1:5000/admin")
        else:
            CustomMessageBox("Server Not Running", "Please start the server before launching the web admin.", "error")

class GenerateView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent, fg_color="transparent")
        self.controller = controller

        ctk.CTkLabel(self, text="Generate Vouchers", font=("Helvetica", 24, "bold")).pack(anchor="w", pady=(0, 20))

        # Selection Frame
        sel_frame = ctk.CTkFrame(self, border_width=2, border_color="#E0E0E0")
        sel_frame.pack(fill=tk.X)
        
        ctk.CTkLabel(sel_frame, text="Select Options", font=("Arial", 14, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", padx=10, pady=5)

        form_frame = ctk.CTkFrame(sel_frame, fg_color="transparent")
        form_frame.grid(row=1, column=0, columnspan=2, sticky="ew", padx=10, pady=10)

        ctk.CTkLabel(form_frame, text="Profile / Plan:").grid(row=0, column=0, sticky="w", pady=5)
        
        self.profile_var = ctk.StringVar()
        self.cb_profiles = ctk.CTkComboBox(form_frame, variable=self.profile_var, state="readonly")
        self.cb_profiles.grid(row=0, column=1, sticky="ew", padx=10)
        
        ctk.CTkLabel(form_frame, text="Qty:").grid(row=1, column=0, sticky="w", pady=5)
        self.qty_var = ctk.StringVar(value="1")
        # Spinbox does not exist in CTK yet, using Entry or option menu. Basic entry for now.
        ctk.CTkEntry(form_frame, textvariable=self.qty_var, width=60).grid(row=1, column=1, sticky="w", padx=10)

        ctk.CTkButton(form_frame, text="Generate", command=self.generate, fg_color="#ffd41d", hover_color="#e6c019", text_color="black", font=("Arial", 12, "bold")).grid(row=2, column=1, padx=10, pady=15, sticky="e")

        # Result
        self.result_frame = ctk.CTkFrame(self, border_width=2, border_color="#E0E0E0")
        self.result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        ctk.CTkLabel(self.result_frame, text="Generated Codes", font=("Arial", 14, "bold")).pack(anchor="w", padx=10, pady=5)
        
        self.result_text = ctk.CTkTextbox(self.result_frame)
        self.result_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))
        self.result_text.configure(state="disabled")

    def refresh(self):
        # Update profiles dropdown
        profiles = [p['name'] for p in self.controller.profiles]
        self.cb_profiles.configure(values=profiles)
        if profiles: self.cb_profiles.set(profiles[0])

    def generate(self):
        profile_name = self.profile_var.get()
        if not profile_name: return
        
        # Find profile
        profile = next((p for p in self.controller.profiles if p['name'] == profile_name), None)
        if not profile: return
        
        # Parse validity from profile to seconds
        try:
            val_str = profile['validity'].lower().strip()
            total_seconds = 0
            if val_str.endswith('h'): total_seconds = int(val_str[:-1]) * 3600
            elif val_str.endswith('d'): total_seconds = int(val_str[:-1]) * 86400
            elif val_str.endswith('m'): total_seconds = int(val_str[:-1]) * 60
            else: total_seconds = int(val_str) * 60 # Default mins
        except:
            CustomMessageBox("Error", "Invalid validity format in profile.", "error")
            return

        qty = int(self.qty_var.get())
        codes = []
        
        with self.controller.flask_app.app_context():
            for _ in range(qty):
                code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                while Voucher.query.filter_by(code=code).first():
                    code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(6))
                
                v = Voucher(code=code, duration=total_seconds)
                db.session.add(v)
                codes.append(f"{code}  ({profile['name']} - {profile['validity']})")
            db.session.commit()

        self.result_text.configure(state="normal")
        self.result_text.insert(tk.END, f"--- NEW BATCH ({datetime.now().strftime('%H:%M:%S')}) ---\n")
        self.result_text.insert(tk.END, "\n".join(codes) + "\n\n")
        self.result_text.configure(state="disabled")


class HotspotView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent, fg_color="transparent")
        self.controller = controller

        # Notebook for Active Users vs Properties
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill=tk.BOTH, expand=True)

        self.tab_users = self.tabview.add("Active Users")
        self.tab_profiles = self.tabview.add("User Profiles")

        self.setup_users_tab()
        self.setup_profiles_tab() # Ensure this is called second or order matters

    def setup_users_tab(self):
        # Tools
        toolbar = ctk.CTkFrame(self.tab_users, fg_color="transparent")
        toolbar.pack(fill=tk.X, pady=(0, 10))
        ctk.CTkButton(toolbar, text="Refresh", command=self.load_users, width=100, fg_color="#4b7178", hover_color="#3a585e", font=("Arial", 12, "bold")).pack(side=tk.LEFT)

        # Treeview Container (for scrollbar)
        tree_frame = ctk.CTkFrame(self.tab_users)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Treeview style
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background="#2a2d2e", foreground="white", fieldbackground="#2a2d2e", borderwidth=0)
        style.map("Treeview", background=[("selected", "#22559b")])
        style.configure("Treeview.Heading", background="#565b5e", foreground="white", relief="flat")
        style.map("Treeview.Heading", background=[("active", "#3484F0")])

        # Treeview
        self.tree_users = ttk.Treeview(tree_frame, columns=("User", "MAC", "Uptime", "Bytes"), show="headings")
        
        # Configure Columns
        self.tree_users.column("User", width=150, anchor="center")
        self.tree_users.column("MAC", width=150, anchor="center")
        self.tree_users.column("Uptime", width=100, anchor="center")
        self.tree_users.column("Bytes", width=150, anchor="center")

        self.tree_users.heading("User", text="User/Code")
        self.tree_users.heading("MAC", text="MAC Address")
        self.tree_users.heading("Uptime", text="Uptime")
        self.tree_users.heading("Bytes", text="Bytes In/Out")
        self.tree_users.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_users.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_users.configure(yscrollcommand=scrollbar.set)

    def load_users(self):
        for i in self.tree_users.get_children(): self.tree_users.delete(i)
        
        with self.controller.flask_app.app_context():
            # Mock data logic combined with DB
            vouchers = Voucher.query.filter(Voucher.activated_at != None).all()
            for v in vouchers:
                if v.remaining_seconds > 0:
                    self.tree_users.insert("", "end", values=(v.code, v.user_mac_address, "Activated", "-"))

    def setup_profiles_tab(self):
        # Toolbar
        toolbar = ctk.CTkFrame(self.tab_profiles, fg_color="transparent")
        toolbar.pack(fill=tk.X, pady=(0, 10))
        
        ctk.CTkButton(toolbar, text="+ New Profile", command=self.open_add_profile, width=120, fg_color="#ffd41d", hover_color="#e6c019", text_color="black", font=("Arial", 12, "bold")).pack(side=tk.LEFT)
        
        # Treeview Container
        tree_frame = ctk.CTkFrame(self.tab_profiles)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        # Profile List
        self.tree_profiles = ttk.Treeview(tree_frame, columns=("Name", "Price", "Validity", "Rate"), show="headings")
        
        # Configure Columns
        self.tree_profiles.column("Name", width=150, anchor="center")
        self.tree_profiles.column("Price", width=100, anchor="center")
        self.tree_profiles.column("Validity", width=100, anchor="center")
        self.tree_profiles.column("Rate", width=150, anchor="center")
        
        self.tree_profiles.heading("Name", text="Name")
        self.tree_profiles.heading("Price", text="Price")
        self.tree_profiles.heading("Validity", text="Validity")
        self.tree_profiles.heading("Rate", text="Rate Limit")
        self.tree_profiles.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree_profiles.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree_profiles.configure(yscrollcommand=scrollbar.set)

    def refresh(self):
        # Reload profiles list
        for i in self.tree_profiles.get_children(): self.tree_profiles.delete(i)
        for p in self.controller.profiles:
            self.tree_profiles.insert("", "end", values=(p['name'], p['price'], p['validity'], f"{p['rate_up']}/{p['rate_down']}"))

    def open_add_profile(self):
        # Modal Dialog styled like screenshot
        top = ctk.CTkToplevel(self.controller)
        top.title("New Profile")
        top.geometry("400x500")
        top.grab_set() # Make modal
        
        # Header
        ctk.CTkLabel(top, text="New Profile", font=("Arial", 20, "bold")).pack(fill=tk.X, pady=(20, 10))

        form = ctk.CTkFrame(top)
        form.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        def add_row(label, row):
            ctk.CTkLabel(form, text=label).grid(row=row, column=0, sticky="e", pady=10, padx=10)
            e = ctk.CTkEntry(form)
            e.grid(row=row, column=1, sticky="ew", pady=10, padx=10)
            return e

        e_name = add_row("Name:", 0)
        e_users = add_row("Shared User:", 1); e_users.insert(0, "1")
        
        # Rate Limit complex row
        ctk.CTkLabel(form, text="Rate Limit:").grid(row=2, column=0, sticky="e", pady=10, padx=10)
        rate_frame = ctk.CTkFrame(form, fg_color="transparent")
        rate_frame.grid(row=2, column=1, sticky="w", padx=10)
        e_rate_up = ctk.CTkEntry(rate_frame, width=60); e_rate_up.pack(side=tk.LEFT); e_rate_up.insert(0, "1M")
        ctk.CTkLabel(rate_frame, text="UL").pack(side=tk.LEFT, padx=2)
        e_rate_down = ctk.CTkEntry(rate_frame, width=60); e_rate_down.pack(side=tk.LEFT, padx=(5,0)); e_rate_down.insert(0, "2M")
        ctk.CTkLabel(rate_frame, text="DL").pack(side=tk.LEFT, padx=2)

        e_validity = add_row("Validity:", 3); e_validity.insert(0, "1h") # Hint: h, d, m
        e_price = add_row("Price:", 4)

        def save():
            try:
                new_p = {
                    "name": e_name.get(),
                    "shared_users": e_users.get(),
                    "rate_up": e_rate_up.get(),
                    "rate_down": e_rate_down.get(),
                    "validity": e_validity.get(),
                    "price": e_price.get()
                }
                self.controller.profiles.append(new_p)
                self.controller.save_profiles()
                self.refresh()
                top.destroy()
            except Exception as e:
                CustomMessageBox("Error", f"Failed to save profile: {e}", "error")
                print(e)

        ctk.CTkButton(top, text="Create", command=save, width=150, fg_color="#ffd41d", hover_color="#e6c019", text_color="black", font=("Arial", 12, "bold")).pack(pady=20)

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, controller):
        ctk.CTkFrame.__init__(self, parent, fg_color="transparent")
        self.controller = controller
        
        ctk.CTkLabel(self, text="Settings", font=("Helvetica", 24, "bold")).pack(anchor="w", pady=(0, 20))
        
        # Router Configuration Frame
        config_frame = ctk.CTkFrame(self, border_width=2, border_color="#E0E0E0")
        config_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkLabel(config_frame, text="MikroTik Router Configuration", font=("Arial", 16, "bold")).pack(anchor="w", padx=15, pady=10)
        
        form_frame = ctk.CTkFrame(config_frame, fg_color="transparent")
        form_frame.pack(fill=tk.X, padx=15, pady=(0, 15))

        self.entries = {}
        
        self.create_entry(form_frame, "Router IP (Host):", "MIKROTIK_HOST", 0)
        self.create_entry(form_frame, "API Port:", "MIKROTIK_PORT", 1)
        self.create_entry(form_frame, "Username:", "MIKROTIK_USER", 2)
        self.create_entry(form_frame, "Password:", "MIKROTIK_PASSWORD", 3, show="*")
        self.create_entry(form_frame, "WAN Interface:", "MIKROTIK_WAN_INTERFACE", 4)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkButton(btn_frame, text="Test Connection", command=self.test_connection, 
                      fg_color="#4b7178", hover_color="#3a585e", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
                      
        ctk.CTkButton(btn_frame, text="Save Settings", command=self.save_settings,
                      fg_color="#ffd41d", hover_color="#e6c019", text_color="black", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
        
        # Database Management Frame
        db_frame = ctk.CTkFrame(self, border_width=2, border_color="#E0E0E0")
        db_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ctk.CTkLabel(db_frame, text="Database Management", font=("Arial", 16, "bold")).pack(anchor="w", padx=15, pady=10)
        
        db_btn_frame = ctk.CTkFrame(db_frame, fg_color="transparent")
        db_btn_frame.pack(fill=tk.X, padx=15, pady=(0, 15))
        
        ctk.CTkButton(db_btn_frame, text="Backup Database", command=self.backup_database,
                      fg_color="#4b7178", hover_color="#3a585e", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
                      
        ctk.CTkButton(db_btn_frame, text="Clear Database", command=self.clear_database,
                      fg_color="#ff5f52", hover_color="#e65549", text_color="white", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=5)
        
        self.load_settings()

    def create_entry(self, parent, label, key, row, show=None):
        ctk.CTkLabel(parent, text=label, width=150, anchor="w").grid(row=row, column=0, padx=5, pady=5, sticky="w")
        entry = ctk.CTkEntry(parent, width=300)
        if show: entry.configure(show=show)
        entry.grid(row=row, column=1, padx=5, pady=5, sticky="w")
        self.entries[key] = entry

    def load_settings(self):
        # Read .env file manually to populate fields
        env_vars = {}
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                for line in f:
                    if '=' in line and not line.strip().startswith('#'):
                        try:
                            key, value = line.strip().split('=', 1)
                            env_vars[key] = value
                        except ValueError: pass
        
        # Set defaults if missing
        defaults = {
            "MIKROTIK_HOST": "192.168.88.1",
            "MIKROTIK_PORT": "8728",
            "MIKROTIK_USER": "admin",
            "MIKROTIK_PASSWORD": "",
            "MIKROTIK_WAN_INTERFACE": "ether1"
        }
        
        for key, entry in self.entries.items():
            val = env_vars.get(key, defaults.get(key, ""))
            # Handle MIKROTIK_USERNAME/USER confusion locally
            if key == "MIKROTIK_USER" and "MIKROTIK_USER" not in env_vars and "MIKROTIK_USERNAME" in env_vars:
                val = env_vars["MIKROTIK_USERNAME"]
                
            entry.delete(0, tk.END)
            entry.insert(0, val)

    def save_settings(self):
        # Read current .env
        lines = []
        if os.path.exists('.env'):
            with open('.env', 'r') as f:
                lines = f.readlines()
        
        new_values = {k: v.get() for k, v in self.entries.items()}
        
        updated_keys = set()
        new_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            if '=' in line_stripped and not line_stripped.startswith('#'):
                key = line_stripped.split('=')[0].strip()
                if key in new_values:
                    new_lines.append(f"{key}={new_values[key]}\n")
                    updated_keys.add(key)
                elif key == "MIKROTIK_USERNAME" and "MIKROTIK_USER" in new_values:
                    # Update legacy USERNAME to USER value
                    new_lines.append(f"MIKROTIK_USERNAME={new_values['MIKROTIK_USER']}\n")
                    # Also ensure MIKROTIK_USER is added later if strictly needed, 
                    # OR we can just update USERNAME and assume config.py might be changed to read USERNAME?
                    # No, let's keep it simple. If USERNAME matches USER logic, treat them as linked.
                    # But distinct keys:
                    # Logic: If .env has USERNAME, update it. If it doesn't have USER, add it.
                    updated_keys.add("MIKROTIK_USERNAME") # Mark as handled so we don't duplicate
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        
        # Append missing keys (like if MIKROTIK_USER was missing but we had USERNAME, we might want to add USER too to match config.py)
        for key, val in new_values.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={val}\n")
                
        try:
            with open('.env', 'w') as f:
                f.writelines(new_lines)
            CustomMessageBox("Success", "Settings saved successfully! Please restart the server.")
        except Exception as e:
            CustomMessageBox("Error", f"Failed to save settings: {e}", "error")

    def test_connection(self):
        import routeros_api
        import threading
        
        # Disable button to prevent multi-click
        # Note: Ideally store reference to button to disable it, but for simplicity we rely on modal behavior
        
        host = self.entries["MIKROTIK_HOST"].get()
        user = self.entries["MIKROTIK_USER"].get()
        password = self.entries["MIKROTIK_PASSWORD"].get()
        wan_iface = self.entries["MIKROTIK_WAN_INTERFACE"].get()
        
        try:
            port = int(self.entries["MIKROTIK_PORT"].get())
        except:
            CustomMessageBox("Error", "Port must be a number.", "error")
            return

        # Update Status Bar
        self.controller.status_label.configure(text="Testing Connection...")
        self.controller.draw_status_indicator("orange")
        self.controller.start_loading_animation()

        def run_test():
            try:
                connection = routeros_api.RouterOsApiPool(host, username=user, password=password, port=port, plaintext_login=True)
                api = connection.get_api()
                identity = api.get_resource('/system/identity').get()
                
                # Check WAN interface
                iface_exists = False
                try:
                    if api.get_resource('/interface').get(name=wan_iface): 
                        iface_exists = True
                except: pass
                
                connection.disconnect()
                name = identity[0].get('name') if identity else 'Unknown'
                
                msg = f"Connected successfully!\nRouter Identity: {name}"
                if iface_exists: msg += f"\nWAN Interface '{wan_iface}' found."
                else: msg += f"\nWarning: WAN Interface '{wan_iface}' NOT found."
                
                self.after(0, lambda: CustomMessageBox("Success", msg))
            except Exception as e:
                err_msg = str(e)
                self.after(0, lambda: CustomMessageBox("Connection Failed", f"Could not connect to router:\n{err_msg}", "error"))
            finally:
                # Restore status bar based on server state
                def restore_status():
                    self.controller.stop_loading_animation()
                    if self.controller.is_server_running:
                        self.controller.draw_status_indicator("#00FF00")
                        self.controller.status_label.configure(text="Server Running: http://127.0.0.1:5000")
                    else:
                        self.controller.draw_status_indicator(("black", "gray"))
                        self.controller.status_label.configure(text="Server Stopped")
                self.after(0, restore_status)

        # Run in thread to not freeze UI
        threading.Thread(target=run_test, daemon=True).start()

    def backup_database(self):
        """Backup the database to instance/backups directory."""
        try:
            from shutil import copy2
            import time
            
            db_path = 'instance/pisonet.db'
            if not os.path.exists(db_path):
                CustomMessageBox("Error", "Database file not found.", "error")
                return
            
            # Create backups directory if it doesn't exist
            backup_dir = 'instance/backups'
            os.makedirs(backup_dir, exist_ok=True)
            
            # Create timestamped backup
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            backup_path = os.path.join(backup_dir, f"app_backup_{timestamp}.db")
            
            copy2(db_path, backup_path)
            CustomMessageBox("Success", f"Database backed up successfully!\n\nBackup location:\n{backup_path}", "info")
            print(f"[BACKUP] Database backed up to {backup_path}")
        except Exception as e:
            CustomMessageBox("Error", f"Failed to backup database:\n{str(e)}", "error")
            print(f"[BACKUP] Error: {str(e)}")

    def clear_database(self):
        """Clear all vouchers from the database with confirmation."""
        # Show confirmation dialog
        root = tk.Tk()
        root.withdraw()
        
        result = messagebox.askyesno(
            "Confirm Database Clear",
            "WARNING: This will delete ALL vouchers from the database.\n\n"
            "This action cannot be undone!\n\n"
            "Do you want to proceed?"
        )
        root.destroy()
        
        if not result:
            return
        
        try:
            with self.controller.flask_app.app_context():
                from app.models import Voucher
                
                # Clear all vouchers
                voucher_count = Voucher.query.count()
                Voucher.query.delete()
                db.session.commit()
                
                # Clear the session cache so new queries get fresh data
                db.session.expunge_all()
                
                CustomMessageBox("Success", f"Database cleared!\n\nDeleted {voucher_count} voucher(s).", "info")
                print(f"[DATABASE] Cleared {voucher_count} voucher(s)")
        except Exception as e:
            db.session.rollback()
            CustomMessageBox("Error", f"Failed to clear database:\n{str(e)}", "error")
            print(f"[DATABASE] Error: {str(e)}")

if __name__ == "__main__":
    app = PisonetManager()
    app.mainloop()
