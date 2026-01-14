def flask_run():
    from app import create_app, db
    app = create_app()
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import threading
import webbrowser
import sys
import os
import json
import secrets
import string
from datetime import datetime, timedelta

# Import Application Logic
sys.path.append(os.getcwd())
from app import create_app, db
from app.models import Voucher, Admin

class PisonetManager(tk.Tk):
    def setup_logging(self):
        import sys
        class TextRedirector:
            def __init__(self, log_func):
                self.log_func = log_func
            def write(self, msg):
                if msg.strip():
                    self.log_func(msg)
            def flush(self):
                pass
        sys.stdout = TextRedirector(self.log_to_gui)
        sys.stderr = TextRedirector(self.log_to_gui)

    def __init__(self):
        super().__init__()

        self.title("HighSpeed Pisonet Manager")
        self.geometry("900x650")
        try:
            self.iconbitmap("app/static/img/favicon.ico")
        except:
            pass

        # App State
        self.flask_process = None
        self.is_server_running = False
        self.profiles_file = 'profiles.json'
        
        # Configure Colors
        self.bg_color = "#F0F0F0"
        self.sidebar_color = "#2E3B55"
        self.configure(bg=self.bg_color)
        
        # Initialize UI
        self.setup_ui()
        self.load_profiles()
        self.setup_logging()

    def setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        
        # Split Layout: Left Sidebar, Right Content
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # 1. Sidebar
        self.sidebar_frame = tk.Frame(self, bg=self.sidebar_color, width=200)
        self.sidebar_frame.grid(row=0, column=0, sticky="ns")
        self.sidebar_frame.grid_propagate(False)

        # Sidebar Header
        lbl_brand = tk.Label(self.sidebar_frame, text="Admin", bg=self.sidebar_color, fg="white", font=("Helvetica", 16, "bold"))
        lbl_brand.pack(pady=20)
        
        # Sidebar Menu Buttons
        self.create_sidebar_btn("Dashboard", self.show_dashboard)
        self.create_sidebar_btn("Generate", self.show_generate)
        self.create_sidebar_btn("Hotspot", self.show_hotspot)
        self.create_sidebar_btn("Settings", self.show_settings)

        # 2. Status Bar (Bottom)
        self.status_bar = tk.Frame(self, bg="#E0E0E0", height=30)
        self.status_bar.grid(row=1, column=0, columnspan=2, sticky="ew")
        
        self.status_indicator = tk.Canvas(self.status_bar, width=15, height=15, bg="#E0E0E0", highlightthickness=0)
        self.status_indicator.pack(side=tk.LEFT, padx=5, pady=5)
        self.draw_status_indicator("black") # Stopped
        
        self.status_label = tk.Label(self.status_bar, text="Server Stopped", bg="#E0E0E0", font=("Arial", 9))
        self.status_label.pack(side=tk.LEFT)

        # 3. Content Area
        self.content_area = tk.Frame(self, bg=self.bg_color)
        self.content_area.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        
        # Define Frames for each view
        self.frames = {}
        for F in (DashboardView, GenerateView, HotspotView, SettingsView):
            frame = F(parent=self.content_area, controller=self)
            self.frames[F.__name__] = frame
            frame.grid(row=0, column=0, sticky="nsew")

        # Show initial view
        self.show_dashboard()

    def create_sidebar_btn(self, text, command):
        btn = tk.Button(self.sidebar_frame, text=text, command=command, 
                        bg=self.sidebar_color, fg="white", bd=0, 
                        font=("Arial", 11), activebackground="#4a5a7d", activeforeground="white",
                        anchor="w", padx=20)
        btn.pack(fill=tk.X, pady=2)

    def show_dashboard(self): self.show_frame("DashboardView")
    def show_generate(self): self.show_frame("GenerateView")
    def show_hotspot(self): self.show_frame("HotspotView")
    def show_settings(self): self.show_frame("SettingsView")

    def show_frame(self, page_name):
        frame = self.frames[page_name]
        frame.tkraise()
        # Refresh if needed
        if hasattr(frame, 'refresh'):
            frame.refresh()

    def draw_status_indicator(self, color):
        self.status_indicator.delete("all")
        self.status_indicator.create_oval(2, 2, 13, 13, fill=color, outline="")

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

        import multiprocessing
        self.flask_process = multiprocessing.Process(target=flask_run)
        self.flask_process.start()
        self.is_server_running = True
        self.draw_status_indicator("#00FF00")
        self.status_label.config(text="Server Running: http://127.0.0.1:5000")
        self.frames["DashboardView"].btn_start.config(state="normal", text="Stop Server")
        self.log_to_gui("Server started at http://127.0.0.1:5000")
        self.after(2000, lambda: webbrowser.open("http://127.0.0.1:5000/admin"))

    def stop_server(self):
        if not self.is_server_running or not self.flask_process:
            return
        try:
            self.flask_process.terminate()
            self.flask_process.join(timeout=5)
            self.log_to_gui("Flask server process terminated.")
        except Exception as e:
            self.log_to_gui(f"Error terminating server: {e}")
        self.is_server_running = False
        self.flask_process = None
        self.draw_status_indicator("black")
        self.status_label.config(text="Server Stopped")
        self.frames["DashboardView"].btn_start.config(state="normal", text="Start Server")
        self.log_to_gui("Server stopped.")

    def log_to_gui(self, msg):
        try:
            frame = self.frames.get("DashboardView")
            if frame and hasattr(frame, "log_area"):
                frame.log_area.insert(tk.END, msg + "\n")
                frame.log_area.see(tk.END)
        except Exception as e:
            print(f"GUI log error: {e}")


class DashboardView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg=controller.bg_color)
        self.controller = controller
        
        lb = tk.Label(self, text="System Dashboard", font=("Helvetica", 18, "bold"), bg=controller.bg_color, fg="#333")
        lb.pack(anchor="w", pady=(0, 20))

        # Controls
        control_frame = tk.LabelFrame(self, text="Services", bg=controller.bg_color, padx=15, pady=15)
        control_frame.pack(fill=tk.X)


        self.btn_start = ttk.Button(control_frame, text="Start Server", command=controller.start_server)
        self.btn_start.pack(side=tk.LEFT, padx=5)

        ttk.Button(control_frame, text="Launch Web Admin", command=lambda: webbrowser.open("http://127.0.0.1:5000/admin")).pack(side=tk.LEFT, padx=5)

        # Logs
        log_frame = tk.LabelFrame(self, text="Logs", bg=controller.bg_color, padx=10, pady=10)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=20)
        
        self.log_area = scrolledtext.ScrolledText(log_frame, height=10)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        self.log_area.insert(tk.END, "Ready...\n")

class GenerateView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg=controller.bg_color)
        self.controller = controller

        tk.Label(self, text="Generate Vouchers", font=("Helvetica", 18, "bold"), bg=controller.bg_color, fg="#333").pack(anchor="w", pady=(0, 20))

        # Selection Frame
        sel_frame = tk.LabelFrame(self, text="Select Options", bg=controller.bg_color, padx=20, pady=20)
        sel_frame.pack(fill=tk.X)

        tk.Label(sel_frame, text="Profile / Plan:", bg=controller.bg_color).grid(row=0, column=0, sticky="w", pady=5)
        
        self.profile_var = tk.StringVar()
        self.cb_profiles = ttk.Combobox(sel_frame, textvariable=self.profile_var, state="readonly")
        self.cb_profiles.grid(row=0, column=1, sticky="ew", padx=10)
        
        tk.Label(sel_frame, text="Qty:", bg=controller.bg_color).grid(row=1, column=0, sticky="w", pady=5)
        self.qty_var = tk.StringVar(value="1")
        tk.Spinbox(sel_frame, from_=1, to=100, textvariable=self.qty_var, width=5).grid(row=1, column=1, sticky="w", padx=10)

        ttk.Button(sel_frame, text="Generate", command=self.generate).grid(row=2, column=1, padx=10, pady=15, sticky="e")

        # Result
        self.result_frame = tk.LabelFrame(self, text="Generated Codes", bg=controller.bg_color, padx=10, pady=10)
        self.result_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        self.result_text = scrolledtext.ScrolledText(self.result_frame)
        self.result_text.pack(fill=tk.BOTH, expand=True)

    def refresh(self):
        # Update profiles dropdown
        profiles = [p['name'] for p in self.controller.profiles]
        self.cb_profiles['values'] = profiles
        if profiles: self.cb_profiles.current(0)

    def generate(self):
        profile_name = self.profile_var.get()
        if not profile_name: return
        
        # Find profile
        profile = next((p for p in self.controller.profiles if p['name'] == profile_name), None)
        if not profile: return
        
        # Parse validity to seconds
        try:
            val_str = profile['validity'].lower().strip()
            total_seconds = 0
            if val_str.endswith('h'): total_seconds = int(val_str[:-1]) * 3600
            elif val_str.endswith('d'): total_seconds = int(val_str[:-1]) * 86400
            elif val_str.endswith('m'): total_seconds = int(val_str[:-1]) * 60
            else: total_seconds = int(val_str) * 60 # Default mins
        except:
            messagebox.showerror("Error", "Invalid validity format in profile.")
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

        self.result_text.insert(tk.END, f"--- NEW BATCH ({datetime.now().strftime('%H:%M:%S')}) ---\n")
        self.result_text.insert(tk.END, "\n".join(codes) + "\n\n")


class HotspotView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg=controller.bg_color)
        self.controller = controller

        # Notebook for Active Users vs Properties
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        self.tab_users = tk.Frame(self.notebook, bg=controller.bg_color)
        self.tab_profiles = tk.Frame(self.notebook, bg=controller.bg_color)
        
        self.notebook.add(self.tab_users, text="Active Users")
        self.notebook.add(self.tab_profiles, text="User Profiles")

        self.setup_profiles_tab()
        self.setup_users_tab()

    def setup_users_tab(self):
        # Tools
        toolbar = tk.Frame(self.tab_users, bg="#ddd", pady=5)
        toolbar.pack(fill=tk.X)
        ttk.Button(toolbar, text="Refresh", command=self.load_users).pack(side=tk.LEFT, padx=5)

        # Treeview
        self.tree_users = ttk.Treeview(self.tab_users, columns=("User", "MAC", "Uptime", "Bytes"), show="headings")
        self.tree_users.heading("User", text="User/Code")
        self.tree_users.heading("MAC", text="MAC Address")
        self.tree_users.heading("Uptime", text="Uptime")
        self.tree_users.heading("Bytes", text="Bytes In/Out")
        self.tree_users.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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
        toolbar = tk.Frame(self.tab_profiles, bg="#ddd", pady=5)
        toolbar.pack(fill=tk.X)
        
        btn_add = tk.Button(toolbar, text="+ New Profile", bg="#0055ff", fg="white", bd=0, padx=10, command=self.open_add_profile)
        btn_add.pack(side=tk.LEFT, padx=10)
        
        # Profile List
        self.tree_profiles = ttk.Treeview(self.tab_profiles, columns=("Name", "Price", "Validity", "Rate"), show="headings")
        self.tree_profiles.heading("Name", text="Name")
        self.tree_profiles.heading("Price", text="Price")
        self.tree_profiles.heading("Validity", text="Validity")
        self.tree_profiles.heading("Rate", text="Rate Limit")
        self.tree_profiles.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    def refresh(self):
        # Reload profiles list
        for i in self.tree_profiles.get_children(): self.tree_profiles.delete(i)
        for p in self.controller.profiles:
            self.tree_profiles.insert("", "end", values=(p['name'], p['price'], p['validity'], f"{p['rate_up']}/{p['rate_down']}"))

    def open_add_profile(self):
        # Modal Dialog styled like screenshot
        top = tk.Toplevel(self.controller)
        top.title("New Profile")
        top.geometry("400x450")
        top.configure(bg="#f0f0f0")
        
        # Header
        tk.Label(top, text="New Profile", bg="#0000aa", fg="white", font=("Arial", 12, "bold"), anchor="w", padx=10).pack(fill=tk.X, ipady=5)

        form = tk.Frame(top, bg="#f0f0f0", padx=20, pady=20)
        form.pack(fill=tk.BOTH, expand=True)

        def add_row(label, row):
            tk.Label(form, text=label, bg="#f0f0f0").grid(row=row, column=0, sticky="e", pady=5, padx=5)
            e = tk.Entry(form)
            e.grid(row=row, column=1, sticky="ew", pady=5)
            return e

        e_name = add_row("Name:", 0)
        e_users = add_row("Shared User:", 1); e_users.insert(0, "1")
        
        # Rate Limit complex row
        tk.Label(form, text="Rate Limit:", bg="#f0f0f0").grid(row=2, column=0, sticky="e", pady=5, padx=5)
        rate_frame = tk.Frame(form, bg="#f0f0f0")
        rate_frame.grid(row=2, column=1, sticky="w")
        e_rate_up = tk.Entry(rate_frame, width=5); e_rate_up.pack(side=tk.LEFT); e_rate_up.insert(0, "1M")
        tk.Label(rate_frame, text="Upload", bg="#f0f0f0", font=("Arial", 7)).pack(side=tk.LEFT)
        e_rate_down = tk.Entry(rate_frame, width=5); e_rate_down.pack(side=tk.LEFT, padx=(5,0)); e_rate_down.insert(0, "2M")
        tk.Label(rate_frame, text="Download", bg="#f0f0f0", font=("Arial", 7)).pack(side=tk.LEFT)

        e_validity = add_row("Validity:", 3); e_validity.insert(0, "1h") # Hint: h, d, m
        e_price = add_row("Price:", 4)

        def save():
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

        tk.Button(top, text="Create", bg="#0000aa", fg="white", command=save, width=15).pack(pady=10)

class SettingsView(tk.Frame):
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent, bg=controller.bg_color)
        tk.Label(self, text="Settings (Placeholder)", bg=controller.bg_color).pack(pady=20)

if __name__ == "__main__":
    app = PisonetManager()
    app.mainloop()
