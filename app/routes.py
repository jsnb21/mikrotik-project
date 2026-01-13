from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_required, current_user, login_user, logout_user
from . import db, login_manager
from .models import Voucher, Admin
from .utils import mikrotik_allow_mac
from datetime import datetime, timezone
from sqlalchemy import func
import string
import secrets

bp = Blueprint('main', __name__)

@login_manager.user_loader
def load_user(user_id):
    return Admin.query.get(int(user_id))

def create_default_admin():
    if not Admin.query.filter_by(username='jsnb').first():
        temp_password = 'temp_password_123' # Temporary password
        admin = Admin(username='jsnb')
        admin.set_password(temp_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Default admin 'jsnb' created with password: {temp_password}")


@bp.route('/login', methods=['GET', 'POST'])
def login():
    # Ensure default admin exists
    create_default_admin()
    
    if current_user.is_authenticated:
        return redirect(url_for('main.admin_dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = Admin.query.filter_by(username=username).first()
        
        if user and user.check_password(password):
            login_user(user)
            return redirect(url_for('main.admin_dashboard'))
        else:
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
    
    # Store in session for use in other routes
    if mac_address:
        session['hotspot_mac'] = mac_address
        session['hotspot_ip'] = ip_address
        session['hotspot_link_orig'] = link_orig
    
    # If called from MikroTik hotspot, use hotspot template
    if mac_address:
        return render_template('voucher_login.html', 
                             mac_address=mac_address,
                             ip_address=ip_address,
                             link_orig=link_orig)
    
    # Check if user has an active session in cookies
    if 'active_code' in session:
        code = session['active_code']
        voucher = Voucher.query.filter_by(code=code).first()
        if voucher and voucher.remaining_seconds > 0:
            return redirect(url_for('main.status_page', code=code))
        else:
            # Clean up expired session
            session.pop('active_code', None)
    
    return render_template('voucher_login.html')

@bp.route('/activate', methods=['POST'])
def activate():
    from flask import session
    code = request.form.get('voucher_code', '').strip().upper()
    
    # Get MAC address from session (passed by MikroTik hotspot), form, or use default
    mac_address = session.get('hotspot_mac') or request.form.get('mac_address') or '00:00:00:00:00:00'
    
    # Basic rate limiting could go here (Redis/memcached) 
    
    voucher = Voucher.query.filter_by(code=code).first()
    
    if not voucher:
        flash("Invalid Voucher Code", "error")
        return redirect(url_for('main.index'))
        
    if voucher.is_activated:
        # Check if it's the same user re-entering the code?
        if voucher.user_mac_address == mac_address and voucher.remaining_seconds > 0:
             session['active_code'] = code # Ensure session is set
             return redirect(url_for('main.status_page', code=code))
        
        flash("Voucher already used or expired", "error")
        return redirect(url_for('main.index'))

    try:
        # Activate Session Logic
        voucher.activate(mac_address)
        db.session.commit()
        
        # Integration with MikroTik
        mikrotik_allow_mac(mac_address, voucher.remaining_seconds)
        
        session['active_code'] = code # Set cookie
        return redirect(url_for('main.status_page', code=code))
        
    except Exception as e:
        db.session.rollback()
        flash(f"Error activating voucher: {str(e)}", "error")
        return redirect(url_for('main.index'))

@bp.route('/status')
def status_page():
    code = request.args.get('code')
    voucher = Voucher.query.filter_by(code=code).first_or_404()
    return render_template('status.html', voucher=voucher)

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
    # Analytics Logic
    now = datetime.now(timezone.utc)
    
    total_vouchers = Voucher.query.count()
    
    # Active: Activated AND Expires in Future
    active_vouchers = Voucher.query.filter(
        Voucher.is_activated == True,
        Voucher.expires_at > now
    ).count()
    
    # Used (Expired): Activated AND Expires in Past
    used_vouchers = Voucher.query.filter(
        Voucher.is_activated == True,
        Voucher.expires_at <= now
    ).count()
    
    # Unused: Not Activated
    unused_vouchers = Voucher.query.filter_by(is_activated=False).count()
    
    # Revenue
    revenue = db.session.query(func.sum(Voucher.price_amount)).filter_by(is_activated=True).scalar() or 0
    
    # Recent Vouchers
    recent_vouchers = Voucher.query.order_by(Voucher.created_at.desc()).limit(20).all()
    
    # All Admins (for management list)
    admins = Admin.query.all()

    return render_template('admin.html', 
                           total=total_vouchers, 
                           active=active_vouchers,
                           used=used_vouchers, 
                           unused=unused_vouchers,
                           revenue=revenue,
                           vouchers=recent_vouchers,
                           admins=admins,
                           current_user=current_user)

@bp.route('/admin/settings')
@login_required
def admin_settings():
    admins = Admin.query.all()
    return render_template('admin_settings.html', admins=admins)

@bp.route('/admin/generate', methods=['POST'])
@login_required
def generate_vouchers():
    amount = int(request.form.get('amount', 10))
    duration = int(request.form.get('duration', 60))
    price = float(request.form.get('price', 10.00))
    
    new_vouchers = []
    for _ in range(amount):
        code = Voucher.generate_code()
        # Ensure uniqueness (simple retry logic)
        while Voucher.query.filter_by(code=code).first():
            code = Voucher.generate_code()
            
        v = Voucher(code=code, duration_minutes=duration, price_amount=price)
        db.session.add(v)
        new_vouchers.append(code)
        
    db.session.commit()
    flash(f"Generated {amount} vouchers.", "success")
    return redirect(url_for('main.admin_dashboard'))

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
    else:
        flash("Password cannot be empty.", "error")
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
