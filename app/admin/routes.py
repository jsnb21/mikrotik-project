from flask import render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from . import admin_bp
from .. import db
from ..models import Admin, Voucher
import string
import secrets
import os
import signal
import subprocess
import sys


@admin_bp.before_request
@login_required
def check_admin_access():
    """Ensure only logged-in admins can access admin routes"""
    if not current_user.is_authenticated:
        return redirect(url_for('main.login'))


@admin_bp.route('/')
def dashboard():
    from ..utils import (
        get_mikrotik_api, 
        get_mikrotik_system_stats, 
        get_mikrotik_active_hotspot_users, 
        get_mikrotik_interface_traffic, 
        get_income_stats,
        get_mikrotik_health,
        get_server_stats
    )
    
    api_pool = get_mikrotik_api()
    try:
        system_stats = get_mikrotik_system_stats(api_pool)
        active_users = get_mikrotik_active_hotspot_users(api_pool)
        traffic = get_mikrotik_interface_traffic(api_pool=api_pool)
        health = get_mikrotik_health(api_pool)
        income_stats = get_income_stats()
        server_stats = get_server_stats()
    finally:
        if api_pool:
            pass

    # Fallback: if RouterOS active list is empty, use locally activated vouchers with time remaining
    if not active_users:
        db_active_users = []
        vouchers = Voucher.query.filter(
            Voucher.activated_at != None,
            Voucher.expires_at != None,
            Voucher.user_mac_address != None
        ).all()
        for v in vouchers:
            if v.remaining_seconds > 0:
                secs = v.remaining_seconds
                hours, rem = divmod(secs, 3600)
                minutes, _ = divmod(rem, 60)
                time_left = f"{hours}h {minutes}m" if hours else f"{minutes}m"
                db_active_users.append({
                    "user": v.code,
                    "mac": v.user_mac_address,
                    "uptime": "Activated",
                    "bytes_in": 0,
                    "bytes_out": 0,
                    "time_left": time_left
                })
        active_users = db_active_users

    # Treat mock uptime marker as disconnected
    connection_ok = system_stats.get('uptime') != 'Offline (Mock)'
    
    admins = Admin.query.all()
    return render_template('dashboard.html', 
                           system_stats=system_stats,
                           active_users=active_users,
                           traffic=traffic,
                           income_stats=income_stats,
                           health=health,
                           server_stats=server_stats,
                           connection_ok=connection_ok,
                           admins=admins,
                           current_user=current_user)


@admin_bp.route('/settings')
def settings():
    admins = Admin.query.all()
    return render_template('settings.html', admins=admins)


@admin_bp.route('/add-admin', methods=['POST'])
def add_admin():
    username = request.form.get('username')
    if Admin.query.filter_by(username=username).first():
        flash('Username already exists', 'error')
        return redirect(url_for('admin.settings'))
    
    alphabet = string.ascii_letters + string.digits
    temp_password = ''.join(secrets.choice(alphabet) for _ in range(8))
    
    new_admin = Admin(username=username)
    new_admin.set_password(temp_password)
    db.session.add(new_admin)
    db.session.commit()
    
    flash(f"Admin '{username}' added. Temp Password: {temp_password}", "success")
    return redirect(url_for('admin.settings'))


@admin_bp.route('/change-password', methods=['POST'])
def change_password():
    new_password = request.form.get('new_password')
    if new_password:
        current_user.set_password(new_password)
        db.session.commit()
        flash("Password updated successfully.", "success")
    return redirect(url_for('admin.settings'))


@admin_bp.route('/reset', methods=['POST'])
def reset_vouchers():
    try:
        num_deleted = db.session.query(Voucher).delete()
        db.session.commit()
        flash(f"Reset complete. Deleted {num_deleted} vouchers.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error resetting vouchers: {str(e)}", "error")
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/server-control/<action>', methods=['POST', 'GET'])
def server_control(action):
    """Control the Flask server: start, stop, or restart.
    Note: GET requests just return status, POST performs action."""
    
    # Handle GET requests (status check)
    if request.method == 'GET':
        return jsonify({
            'success': True,
            'message': 'Server is running',
            'status': 'online'
        }), 200
    
    # Handle POST requests (control actions)
    try:
        if action == 'stop':
            # Stop the Flask server gracefully
            func = request.environ.get('werkzeug.server.shutdown')
            if func is None:
                # Running in production mode, try to kill the process
                if sys.platform.startswith('win'):
                    os.system('taskkill /F /PID %d' % os.getpid())
                else:
                    os.kill(os.getpid(), signal.SIGTERM)
                return jsonify({'success': True, 'message': 'Server stopping...'}), 200
            else:
                func()
                return jsonify({'success': True, 'message': 'Server stopped successfully'}), 200
        
        elif action == 'restart':
            # For restart, just return success - actual restart needs external process
            return jsonify({
                'success': True, 
                'message': 'Server restart initiated. Please wait...'
            }), 200
        
        elif action == 'start':
            # Server is already running if we can respond
            return jsonify({
                'success': True, 
                'message': 'Server is already running'
            }), 200
        
        else:
            return jsonify({
                'success': False, 
                'message': 'Invalid action. Use: start, stop, or restart'
            }), 400
    
    except Exception as e:
        print(f"[ERROR] Server control failed: {str(e)}")
        return jsonify({
            'success': False, 
            'message': f'Error: {str(e)}'
        }), 500
