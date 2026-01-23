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


@admin_bp.route('/api/profiles', methods=['GET'])
def get_profiles():
    """Get list of available voucher profiles"""
    import json
    profiles_file = 'profiles.json'
    
    try:
        if os.path.exists(profiles_file):
            with open(profiles_file, 'r') as f:
                profiles = json.load(f)
        else:
            profiles = []
        return jsonify(profiles)
    except Exception as e:
        return jsonify([]), 500


@admin_bp.route('/api/generate-vouchers', methods=['POST'])
def generate_vouchers():
    """Generate vouchers based on selected profile"""
    import json
    
    try:
        data = request.get_json()
        profile_name = data.get('profile')
        quantity = int(data.get('quantity', 1))
        
        if not profile_name:
            return jsonify({'success': False, 'error': 'Profile name is required'}), 400
            
        if quantity < 1 or quantity > 100:
            return jsonify({'success': False, 'error': 'Quantity must be between 1 and 100'}), 400
        
        # Load profiles
        profiles_file = 'profiles.json'
        if not os.path.exists(profiles_file):
            return jsonify({'success': False, 'error': 'Profiles file not found'}), 404
            
        with open(profiles_file, 'r') as f:
            profiles = json.load(f)
        
        # Find the selected profile
        profile = next((p for p in profiles if p['name'] == profile_name), None)
        if not profile:
            return jsonify({'success': False, 'error': 'Profile not found'}), 404
        
        # Parse validity to seconds
        validity_str = profile['validity']
        if validity_str.endswith('m'):
            duration_seconds = int(validity_str[:-1]) * 60
        elif validity_str.endswith('h'):
            duration_seconds = int(validity_str[:-1]) * 3600
        elif validity_str.endswith('d'):
            duration_seconds = int(validity_str[:-1]) * 86400
        else:
            return jsonify({'success': False, 'error': 'Invalid validity format'}), 400
        
        # Generate vouchers
        voucher_codes = []
        for _ in range(quantity):
            code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            voucher = Voucher(code=code, duration=duration_seconds)
            db.session.add(voucher)
            voucher_codes.append(code)
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'vouchers': voucher_codes,
            'profile': profile_name,
            'quantity': quantity
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500