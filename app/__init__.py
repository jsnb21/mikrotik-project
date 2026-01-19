from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
scheduler = None

def check_expired_vouchers():
    """Background job to disconnect expired vouchers."""
    from .models import Voucher
    from .utils import mikrotik_revoke_mac
    from datetime import datetime, timezone
    
    try:
        # Query activated vouchers that are expired and still have a user MAC assigned
        expired_vouchers = Voucher.query.filter(
            Voucher.activated_at != None,
            Voucher.expires_at != None,
            Voucher.user_mac_address != None,  # Only process if user_mac is still set
            Voucher.is_developer == False
        ).all()
        
        now = datetime.now(timezone.utc)
        disconnected_count = 0
        
        for voucher in expired_vouchers:
            # Check if actually expired
            expires_at = voucher.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            
            remaining = (expires_at - now).total_seconds()
            
            if remaining <= 0:  # Expired
                mac_address = voucher.user_mac_address
                # Voucher has expired, revoke access
                if mikrotik_revoke_mac(mac_address):
                    # Clear user_mac to mark as disconnected (prevent reprocessing)
                    voucher.user_mac_address = None
                    db.session.commit()
                    print(f"[SCHEDULER] Disconnected expired voucher: {voucher.code} (MAC: {mac_address}, expired {abs(remaining):.0f}s ago)")
                    disconnected_count += 1
            else:
                # Log active vouchers with time remaining (optional, helpful for debugging)
                if remaining < 30:  # Only log if less than 30 seconds remaining
                    print(f"[SCHEDULER] Voucher {voucher.code} expiring in {remaining:.0f}s")
        
        if disconnected_count > 0:
            print(f"[SCHEDULER] Disconnected {disconnected_count} expired voucher(s)")
    except Exception as e:
        print(f"[SCHEDULER] Error checking expired vouchers: {str(e)}")

def check_fup():
    """Background job to check FUP limits."""
    from .utils import get_all_active_users, set_hotspot_user_profile
    
    try:
        active_users = get_all_active_users()
        for user in active_users:
            try:
                # Convert bytes to GB (MikroTik returns bytes-out)
                bytes_out = int(user.get('bytes-out', 0))
                usage_gb = bytes_out / (1024**3)
                
                if usage_gb > 50: # 50GB Threshold
                    # Move to Limited Profile
                    username = user.get('name') or user.get('user')
                    if username:
                        set_hotspot_user_profile(username, "Limited")
                        print(f"[FUP] User {username} exceeded 50GB. Moved to Limited profile.")
            except Exception as inner_e:
                print(f"[FUP] Error processing user {user}: {inner_e}")
                
    except Exception as e:
        print(f"[SCHEDULER] Error checking FUP: {str(e)}")

def check_fup_with_context(app):
    with app.app_context():
        check_fup()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Allow requests from your domain and local IP
    app.config['SERVER_NAME'] = None  # Don't enforce SERVER_NAME, allow all hosts
    app.config['TRUSTED_HOSTS'] = ['192.168.88.254', 'neuronet.ai', '*.neuronet.ai']

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from .models import Admin, Voucher  # Import models so db.create_all() works
        db.create_all()
        
        # Initialize scheduler for automatic voucher expiration
        global scheduler
        if scheduler is None:
            scheduler = BackgroundScheduler(daemon=True)
            # Check for expired vouchers every 15 seconds
            scheduler.add_job(func=lambda: check_expired_vouchers_with_context(app), 
                            trigger="interval", 
                            seconds=15,
                            id='check_expired_vouchers',
                            replace_existing=True)
            
            # Check FUP every 5 minutes
            scheduler.add_job(func=lambda: check_fup_with_context(app),
                            trigger="interval",
                            minutes=5,
                            id='check_fup',
                            replace_existing=True)
                            
            scheduler.start()
            print("[SCHEDULER] Started automatic voucher expiration monitor and FUP check")
            
            # Shutdown scheduler when app exits
            atexit.register(lambda: scheduler.shutdown())

    # Register Blueprint
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    return app

def check_expired_vouchers_with_context(app):
    """Wrapper to run check_expired_vouchers with Flask app context."""
    with app.app_context():
        check_expired_vouchers()
