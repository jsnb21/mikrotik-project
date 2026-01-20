from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from . import db, login_manager
from .models import Admin, Voucher
from .utils import (
    get_mikrotik_system_stats, 
    get_all_active_users, 
    get_mikrotik_interface_traffic,
    get_income_stats,
    mikrotik_allow_mac,
    get_mac_from_active_session,
    add_hotspot_user,
    get_mikrotik_active_hotspot_users
)
from datetime import datetime, timezone, timedelta
import string
import secrets
from sqlalchemy import func

bp = Blueprint('main', __name__)

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

def create_default_admin():
    # Check for requested default admin
    if not Admin.query.filter_by(username='admin').first():
        default_password = 'admin123' 
        admin = Admin(username='admin')
        admin.set_password(default_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Default admin 'admin' created with password: {default_password}")


@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Ensure default admin exists
    create_default_admin()
    
    if current_user.is_authenticated:
        return redirect(url_for('main.admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Login attempt: username={username}")
        user = Admin.query.filter_by(username=username).first()
        print(f"User found: {user}")
        
        if user and user.check_password(password):
            print("Password check passed")
            login_user(user)
            return redirect(url_for('main.admin_dashboard'))
        else:
            if user:
                print("Password check failed")
            else:
                print("User not found")
            flash('Invalid username or password', 'error')
            
    return render_template('login.html')

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('main.login'))

@bp.route('/')
def index():
    # Capture MikroTik hotspot parameters
    mac_address = request.args.get('mac', '') or request.form.get('mac', '')
    ip_address = request.args.get('ip', '') or request.form.get('ip', '')
    link_orig = request.args.get('link-orig', '') or request.form.get('link-orig', '')
    client_ip = request.remote_addr
    
    # Store in session for use in other routes
    if mac_address:
        session['hotspot_mac'] = mac_address
        session['hotspot_ip'] = ip_address
        session['hotspot_link_orig'] = link_orig
    
    # Check if user has an active session in cookies
    if 'active_code' in session:
        code = session['active_code']
        voucher = Voucher.query.filter_by(code=code).first()
        if voucher and voucher.remaining_seconds > 0:
            current_app.logger.info("Index: Found active code in session, redirecting to status: code=%s", code)
            return redirect(url_for('main.status_page', code=code))
        else:
            # Clean up expired session
            current_app.logger.info("Index: Active code expired or not found, cleaning up: code=%s", code)
            session.pop('active_code', None)
            session.modified = True  # Ensure session changes are saved
    
    # If no MAC from hotspot params, try to get from MikroTik active sessions by IP
    if not mac_address:
        mac_address = get_mac_from_active_session(client_ip)
    
    # Check if MAC address has an active voucher
    if mac_address:
        active_voucher = Voucher.query.filter(
            Voucher.user_mac_address == mac_address,
            Voucher.activated_at != None
        ).order_by(Voucher.expires_at.desc()).first()
        
        if active_voucher and active_voucher.remaining_seconds > 0:
            session['active_code'] = active_voucher.code
            session['hotspot_mac'] = mac_address  # Store MAC in session
            current_app.logger.info("Index: Redirecting to status: code=%s MAC=%s", active_voucher.code, mac_address)
            return redirect(url_for('main.status_page', code=active_voucher.code))

    # If called from MikroTik hotspot, use hotspot template
    if mac_address:
        return render_template('voucher_login.html', 
                             mac_address=mac_address,
                             ip_address=ip_address,
                             link_orig=link_orig)
    
    return render_template('index.html')

@bp.route('/design')
def design_view():
    """Route for designing the login page without a physical MikroTik router"""
    return render_template('voucher_login.html', 
                         mac_address="00:11:22:33:44:55",
                         ip_address="192.168.88.254",
                         link_orig="http://www.google.com")

@bp.route('/activate', methods=['POST'])
def activate():
    from flask import session
    code = request.form.get('voucher_code', '').strip()
    
    # Log incoming activation attempt
    current_app.logger.info("Activate attempt: code=%s", code)

    # Get MAC address from session (passed by MikroTik hotspot), form, or use default
    mac_address = session.get('hotspot_mac') or request.form.get('mac_address') or request.remote_addr
    
    voucher = Voucher.query.filter_by(code=code, status='unused').first()
    
    if not voucher:
        flash('Invalid or used voucher code', 'error')
        return redirect(url_for('main.login'))

    # Activate in DB
    now = datetime.now()
    expiry = now + timedelta(days=voucher.duration_days)
    
    voucher.status = 'active'
    voucher.mac_address = mac_address
    voucher.activated_at = now
    voucher.expiry_date = expiry
    voucher.expires_at = expiry # Keep for compatibility if needed, or remove if model updated fully
    
    # Add to MikroTik
    # Password = voucher code (same as username for easy login)
    success = add_hotspot_user(
        name=code,
        password=code,  # Use voucher code as password
        profile="Standard", # Default profile
        comment=f"Expiry: {expiry.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    if success:
        db.session.commit()
        flash('Voucher activated successfully! You are connected.', 'success')
        # Redirect to status page or MikroTik login acting as success
        return redirect(url_for('main.status_page', code=code))
    else:
        db.session.rollback()
        flash('Failed to activate voucher on Network. Please try again.', 'error')
        return redirect(url_for('main.login'))
@bp.route('/status')
def status_page():
    code = request.args.get('code')
    # Disable query caching to ensure fresh data from database
    voucher = Voucher.query.filter_by(code=code).first_or_404()
    db.session.expunge(voucher)  # Remove from session cache
    voucher = Voucher.query.filter_by(code=code).first_or_404()  # Re-query fresh
    return render_template('status.html', voucher=voucher, is_developer=voucher.is_developer)

@bp.route('/end-session', methods=['POST'])
def end_session():
    """End the current session and clear the active code"""
    code = request.form.get('code')
    voucher = Voucher.query.filter_by(code=code).first()
    
    if voucher:
        # Reset activation for developer codes only
        if voucher.is_developer:
            voucher.activated_at = None
            voucher.expires_at = None
            voucher.user_mac_address = None
            db.session.commit()
            current_app.logger.info("Developer session ended: code=%s", code)
        else:
            current_app.logger.warning("Attempted to end non-developer voucher: code=%s", code)
    
    # Clear session
    session.pop('active_code', None)
    session.pop('hotspot_mac', None)
    session.pop('hotspot_ip', None)
    session.pop('hotspot_link_orig', None)
    
    return redirect(url_for('main.index'))

@bp.route('/api/status/<code_or_mac>')
def api_status(code_or_mac):
    """API Generic Endpoint for status check via Ajax"""
    # Try finding by code first
    voucher = Voucher.query.filter_by(code=code_or_mac).first()
    if not voucher:
        # Try finding by active session MAC (most effective for captive portal)
        # Note: This is simplified. Users might have multiple used vouchers. 
        # We want the currently active one.
        now = datetime.now(timezone.utc)
        voucher = Voucher.query.filter(
            Voucher.user_mac_address == code_or_mac,
            Voucher.expires_at > now
        ).order_by(Voucher.expires_at.desc()).first()

    if not voucher:
        return jsonify({'active': False, 'remaining_seconds': 0})
        
    return jsonify({
        'active': voucher.remaining_seconds > 0,
        'remaining_seconds': voucher.remaining_seconds,
        'mac': voucher.user_mac_address,
        'expiry_time': voucher.expires_at.isoformat() if voucher.expires_at else None
    })

# --- Admin Routes ---

@bp.route('/admin')
@login_required
def admin_dashboard():
    # Fetch Analytics from MikroTik - use single connection for all calls
    from .utils import get_mikrotik_api
    api_pool = get_mikrotik_api()
    
    try:
        system_stats = get_mikrotik_system_stats(api_pool)
        active_users = get_mikrotik_active_hotspot_users(api_pool)
        traffic = get_mikrotik_interface_traffic(api_pool=api_pool)
        income_stats = get_income_stats()
    finally:
        if api_pool:
            try:
                api_pool.disconnect()
            except:
                pass
    
    # Calculate Revenue (Sum of price for used vouchers)
    revenue = db.session.query(func.sum(Voucher.price)).filter(Voucher.status != 'unused').scalar() or 0
    
    # 5-Day Reminder (Active vouchers expiring in <= 5 days)
    now = datetime.now()
    five_days_from_now = now + timedelta(days=5)
    expiring_vouchers = Voucher.query.filter(
        Voucher.status == 'active',
        Voucher.expiry_date <= five_days_from_now,
        Voucher.expiry_date >= now
    ).all()

    # Fetch all admins for the dashboard
    admins = Admin.query.all()

    return render_template('admin.html', 
                           system_stats=system_stats,
                           active_users=active_users,
                           traffic=traffic,
                           income_stats=income_stats,
                           revenue=revenue,
                           expiring_vouchers=expiring_vouchers,
                           admins=admins,
                           current_user=current_user)

@bp.route('/admin/settings')
@login_required
def admin_settings():
    admins = Admin.query.all()
    return render_template('admin_settings.html', admins=admins)

@bp.route('/admin/add-admin', methods=['POST'])
@login_required
def add_admin():
    username = request.form.get('username')
    if Admin.query.filter_by(username=username).first():
        flash('Username already exists', 'error')
        return redirect(url_for('main.admin_settings'))
    
    # Generate random temp password
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(8))
    
    new_admin = Admin(username=username)
    new_admin.set_password(temp_password)
    db.session.add(new_admin)
    db.session.commit()
    
    flash(f"Admin '{username}' added. Temp Password: {temp_password}", "success")
    return redirect(url_for('main.admin_settings'))

@bp.route('/admin/change-password', methods=['POST'])
@login_required
def change_password():
    new_password = request.form.get('new_password')
    if new_password:
        current_user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully.", "success")
    return redirect(url_for('main.admin_settings'))

@bp.route('/admin/reset', methods=['POST'])
@login_required
def reset_vouchers():
    # Dangerous action: Deletes ALL vouchers
    try:
        num_deleted = db.session.query(Voucher).delete()
        db.session.commit()
        flash(f"Reset complete. Deleted {num_deleted} vouchers.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error resetting vouchers: {str(e)}", "error")
        
    return redirect(url_for('main.admin_dashboard'))


@bp.route('/test', methods=['GET', 'POST'])
def test_connection():
    """Test endpoint to verify phone can communicate with Flask server"""
    try:
        # Try to get JSON data, but don't fail if it's not there
        if request.method == 'POST':
            data = request.get_json(silent=True) or {}
        else:
            data = {'method': 'GET'}
        
        # Get client information
        client_ip = request.remote_addr
        user_agent = request.headers.get('User-Agent', 'Unknown')
        host = request.headers.get('Host', 'Unknown')
        
        # Log the connection attempt in terminal
        print("=" * 60)
        print("🔔 TEST CONNECTION RECEIVED!")
        print("=" * 60)
        print(f"📱 Client IP: {client_ip}")
        print(f"🌐 User Agent: {user_agent}")
        print(f"🏠 Host Header: {host}")
        print(f"📦 Data received: {data}")
        print(f"🔧 Method: {request.method}")
        print("=" * 60)
        
        # Send success response back to phone
        response_data = {
            'status': 'success',
            'message': 'Connection successful! Flask received your request.',
            'server_time': datetime.now(timezone.utc).isoformat(),
            'client_ip': client_ip,
            'host': host,
            'method': request.method,
            'data_received': data
        }
        
        return jsonify(response_data), 200
    except Exception as e:
        print(f"❌ ERROR in test endpoint: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500


@bp.route('/api/activate', methods=['POST', 'OPTIONS'])
def api_activate():
    """API endpoint for activating vouchers from MikroTik login page.
    This allows the MikroTik login.html to activate a voucher and create
    the hotspot user before submitting to MikroTik's login system.
    """
    # Handle CORS preflight
    if request.method == 'OPTIONS':
        response = jsonify({'status': 'ok'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response
    
    try:
        data = request.get_json() or {}
        code = (data.get('voucher_code') or '').strip().upper()
        mac_address = data.get('mac_address') or request.remote_addr
        ip_address = data.get('ip_address') or request.remote_addr
        
        print(f"[API] Activate request: code={code}, mac={mac_address}, ip={ip_address}")
        
        if not code or len(code) < 6:
            response = jsonify({'success': False, 'message': 'Invalid voucher code'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # Check if voucher exists
        voucher = Voucher.query.filter_by(code=code).first()
        
        if not voucher:
            response = jsonify({'success': False, 'message': 'Voucher not found'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 404
        
        # Check if already activated
        if voucher.status == 'active' and voucher.activated_at:
            # Already active - check if expired
            if voucher.remaining_seconds > 0:
                # Still valid, allow login
                response = jsonify({
                    'success': True, 
                    'message': 'Voucher already active',
                    'remaining_seconds': voucher.remaining_seconds
                })
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 200
            else:
                response = jsonify({'success': False, 'message': 'Voucher has expired'})
                response.headers.add('Access-Control-Allow-Origin', '*')
                return response, 400
        
        if voucher.status == 'used':
            response = jsonify({'success': False, 'message': 'Voucher already used'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 400
        
        # Activate the voucher
        now = datetime.now()
        expiry = now + timedelta(days=voucher.duration_days)
        
        voucher.status = 'active'
        voucher.mac_address = mac_address
        voucher.user_mac_address = mac_address
        voucher.activated_at = now
        voucher.expiry_date = expiry
        voucher.expires_at = expiry
        
        # Create MikroTik hotspot user
        success = add_hotspot_user(
            name=code,
            password=code,  # Password = voucher code
            profile="Standard",
            comment=f"Expiry: {expiry.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        if success:
            db.session.commit()
            print(f"[API] Voucher {code} activated successfully")
            response = jsonify({
                'success': True, 
                'message': 'Voucher activated! You can now login.',
                'code': code
            })
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 200
        else:
            db.session.rollback()
            print(f"[API] Failed to create hotspot user for {code}")
            response = jsonify({'success': False, 'message': 'Network error. Please try again.'})
            response.headers.add('Access-Control-Allow-Origin', '*')
            return response, 500
            
    except Exception as e:
        print(f"[API] Error: {str(e)}")
        response = jsonify({'success': False, 'message': 'Server error'})
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response, 500


@bp.route('/info')
def server_info():
    """Show server information to help with connection"""
    import socket
    hostname = socket.gethostname()
    local_ip = socket.gethostbyname(hostname)
    
    info = f"""
    <html>
    <head>
        <title>Flask Server Info</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial; padding: 20px; background: #f0f0f0; }}
            .box {{ background: white; padding: 20px; border-radius: 10px; margin: 10px 0; }}
            h2 {{ color: #2563eb; }}
            code {{ background: #e5e7eb; padding: 5px 10px; border-radius: 5px; display: block; margin: 5px 0; }}
        </style>
    </head>
    <body>
        <div class="box">
            <h2>✅ Flask is Running!</h2>
            <p><strong>Server IP:</strong> <code>{local_ip}</code></p>
            <p><strong>Port:</strong> <code>5000</code></p>
            <p><strong>Your IP:</strong> <code>{request.remote_addr}</code></p>
        </div>
        <div class="box">
            <h2>📱 Access from Phone:</h2>
            <p>Use this URL on your phone:</p>
            <code>http://{local_ip}:5000/</code>
        </div>
        <div class="box">
            <h2>🧪 Test Endpoint:</h2>
            <code>http://{local_ip}:5000/test</code>
            <p><a href="/test" style="background: #2563eb; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; display: inline-block; margin-top: 10px;">Test Now</a></p>
        </div>
    </body>
    </html>
    """
    return info
