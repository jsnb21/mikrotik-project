from flask import render_template, request, jsonify, redirect, url_for, flash, session, current_app
from . import client_bp
from .. import db
from ..models import Voucher
from ..utils import (
    get_mikrotik_active_hotspot_users,
    mikrotik_allow_mac,
    get_mac_from_active_session
)
from datetime import datetime, timezone
import socket
import threading
from flask import make_response

def authorize_mikrotik_background(app, code, mac_address, duration):
    """Background thread to authorize MAC with MikroTik using its own app context"""
    with app.app_context():
        try:
            app.logger.info("[BG] Starting MikroTik authorization for %s (MAC: %s)", code, mac_address)
            mikrotik_allow_mac(mac_address, duration)
            app.logger.info("[BG] MikroTik authorization succeeded for %s", code)
        except Exception as e:
            app.logger.exception("[BG] MikroTik authorization failed for %s: %s", code, str(e))


@client_bp.route('/ping')
def ping():
    """Fast, no-cache ping to detect connectivity after bypass."""
    resp = make_response(jsonify({'ok': True, 'server_time': datetime.now(timezone.utc).isoformat()}))
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    return resp


@client_bp.route('/')
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
            return redirect(url_for('client.status_page', code=code))
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
            return redirect(url_for('client.status_page', code=active_voucher.code))

    # If called from MikroTik hotspot, use hotspot template
    if mac_address:
        return render_template('voucher_login.html', 
                             mac_address=mac_address,
                             ip_address=ip_address,
                             link_orig=link_orig)
    
    return render_template('index.html')


@client_bp.route('/design')
def design_view():
    """Route for designing the login page without a physical MikroTik router"""
    return render_template('voucher_login.html', 
                         mac_address="00:11:22:33:44:55",
                         ip_address="192.168.88.254",
                         link_orig="http://www.google.com")


@client_bp.route('/api/activate-quick', methods=['POST'])
def activate_quick():
    """Fast activation endpoint - validates and queues MikroTik authorization in background"""
    code = request.form.get('voucher_code', '').strip().upper()
    mac_address = session.get('hotspot_mac') or request.form.get('mac_address') or '00:00:00:00:00:00'
    
    current_app.logger.info("[QUICK] Activate attempt: code=%s, mac=%s", code, mac_address)
    
    # FAST VALIDATION ONLY (no MikroTik calls)
    voucher = Voucher.query.filter_by(code=code).first()
    
    if not voucher:
        current_app.logger.warning("[QUICK] Voucher not found: %s", code)
        return jsonify({'success': False, 'error': 'Invalid voucher code'}), 400
    
    if voucher.is_activated:
        current_app.logger.info("[QUICK] Voucher already activated: %s", code)
        if voucher.user_mac_address == mac_address and voucher.remaining_seconds > 0:
            return jsonify({'success': True, 'message': 'Already activated'}), 200
        return jsonify({'success': False, 'error': 'Voucher already used'}), 400
    
    try:
        # Quick database activation (no MikroTik yet)
        current_app.logger.info("[QUICK] Quick-activating voucher %s for MAC %s", code, mac_address)
        voucher.activate(mac_address)
        db.session.commit()
        
        # Start MikroTik authorization in background thread with app context
        flask_app = current_app._get_current_object()
        thread = threading.Thread(
            target=authorize_mikrotik_background,
            args=(flask_app, code, mac_address, voucher.duration),
            daemon=True
        )
        thread.start()
        
        session['active_code'] = code
        return jsonify({'success': True, 'message': 'Activation in progress'}), 200
        
    except Exception as e:
        current_app.logger.exception("[QUICK] Error in quick activation: %s", code)
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500


@client_bp.route('/activate', methods=['POST'])
def activate():
    code = request.form.get('voucher_code', '').strip().upper()
    
    # Log incoming activation attempt
    current_app.logger.info("Activate attempt: code=%s, form_keys=%s, session_has_hotspot=%s", code, list(request.form.keys()), 'hotspot_mac' in session)

    # Get MAC address from session (passed by MikroTik hotspot), form, or use default
    mac_address = session.get('hotspot_mac') or request.form.get('mac_address')
    
    # Ensure MAC is persisted in session so we stay in "hotspot mode" on redirect
    if mac_address:
         session['hotspot_mac'] = mac_address
    else:
         mac_address = '00:00:00:00:00:00'
    
    # Basic rate limiting could go here (Redis/memcached) 
    
    voucher = Voucher.query.filter_by(code=code).first()
    
    if not voucher:
        current_app.logger.warning("Activate failed: voucher not found code=%s", code)
        flash("Invalid/Expired Voucher Code", "error")
        # Ensure mac_address is available for the template
        mac_address = session.get('hotspot_mac') or request.form.get('mac_address')
        return render_template('voucher_login.html', 
                             mac_address=mac_address,
                             ip_address=session.get('hotspot_ip'),
                             link_orig=session.get('hotspot_link_orig'))
        
    if voucher.is_activated:
        current_app.logger.info("Voucher already activated: code=%s, mac=%s, remaining=%s", code, voucher.user_mac_address, voucher.remaining_seconds)
        # Check if it's the same user re-entering the code?
        if voucher.user_mac_address == mac_address and voucher.remaining_seconds > 0:
             session['active_code'] = code # Ensure session is set
             return redirect(url_for('client.status_page', code=code))
        
        flash("Voucher already used or expired", "error")
        # Ensure mac_address is available for the template
        mac_address = session.get('hotspot_mac') or request.form.get('mac_address')
        return render_template('voucher_login.html', 
                             mac_address=mac_address,
                             ip_address=session.get('hotspot_ip'),
                             link_orig=session.get('hotspot_link_orig'))

    try:
        # Integration with MikroTik FIRST - authorize before activating in database
        current_app.logger.info("Authorizing MAC %s on MikroTik for voucher %s", mac_address, code)
        try:
            mikrotik_allow_mac(mac_address, voucher.duration)  # Use voucher.duration for initial authorization
        except Exception as e:
            current_app.logger.exception("mikrotik_allow_mac failed for %s", mac_address)
            flash("Failed to authorize with router. Please check MikroTik connection and try again.", "error")
            mac_address = session.get('hotspot_mac') or request.form.get('mac_address')
            return render_template('voucher_login.html', 
                                 mac_address=mac_address,
                                 ip_address=session.get('hotspot_ip'),
                                 link_orig=session.get('hotspot_link_orig'))
        
        # Only activate in database after MikroTik authorization succeeds
        current_app.logger.info("Activating voucher %s for MAC %s", code, mac_address)
        voucher.activate(mac_address)
        db.session.commit()
        db.session.refresh(voucher)  # Refresh to ensure object is synced with database
        current_app.logger.info("Activated voucher %s (developer=%s): activated_at=%s expires_at=%s remaining=%s", voucher.code, voucher.is_developer, voucher.activated_at, voucher.expires_at, voucher.remaining_seconds)
        
        session['active_code'] = code # Set cookie
        return redirect(url_for('client.status_page', code=code))
        
    except Exception as e:
        current_app.logger.exception("Error activating voucher %s", code)
        db.session.rollback()
        flash(f"Error activating voucher: {str(e)}", "error")
        return redirect(url_for('client.index'))


@client_bp.route('/check-status', methods=['POST'])
def check_status():
    """Check status by voucher code"""
    code = request.form.get('voucher_code', '').strip().upper()
    
    if not code:
        flash("Please enter a voucher code", "error")
        return redirect(url_for('client.index'))
    
    voucher = Voucher.query.filter_by(code=code).first()
    
    if not voucher:
        flash("Invalid voucher code", "error")
        return redirect(url_for('client.index'))
    
    if not voucher.is_activated:
        flash("This voucher has not been activated yet", "error")
        return redirect(url_for('client.index'))
    
    # Redirect to status page
    return redirect(url_for('client.status_page', code=code))


@client_bp.route('/status')
def status_page():
    code = request.args.get('code')
    
    # If no code provided, try to auto-detect from MAC address
    if not code:
        # Try to get MAC from session or MikroTik
        mac_address = session.get('hotspot_mac') or request.args.get('mac')
        if not mac_address:
            # Try to get from MikroTik active sessions by IP
            client_ip = request.remote_addr
            mac_address = get_mac_from_active_session(client_ip)
        
        if mac_address:
            # Find active voucher for this MAC
            voucher = Voucher.query.filter(
                Voucher.user_mac_address == mac_address,
                Voucher.activated_at != None
            ).order_by(Voucher.expires_at.desc()).first()
            
            if voucher and voucher.remaining_seconds > 0:
                current_app.logger.info("Status: Auto-detected voucher %s for MAC %s", voucher.code, mac_address)
                # Redirect to status page with code for clean URL
                return redirect(url_for('client.status_page', code=voucher.code))
        
        # No code and couldn't detect - show error or redirect to login
        flash("No active session found. Please enter your voucher code.", "error")
        return redirect(url_for('client.index'))
    
    # Disable query caching to ensure fresh data from database
    voucher = Voucher.query.filter_by(code=code).first_or_404()
    db.session.expunge(voucher)  # Remove from session cache
    voucher = Voucher.query.filter_by(code=code).first_or_404()  # Re-query fresh
    return render_template('status.html', voucher=voucher, is_developer=voucher.is_developer)


@client_bp.route('/end-session', methods=['POST'])
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
    
    return redirect(url_for('client.index'))


@client_bp.route('/api/status/<code_or_mac>')
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


@client_bp.route('/test', methods=['GET', 'POST'])
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


@client_bp.route('/info')
def server_info():
    """Show server information to help with connection"""
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
