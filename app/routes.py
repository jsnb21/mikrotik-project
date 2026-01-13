from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session
from flask_login import login_user, logout_user, login_required, current_user
from . import db, login_manager
from .models import Admin
from .utils import (
    get_mikrotik_system_stats, 
    get_mikrotik_active_hotspot_users, 
    get_mikrotik_interface_traffic,
    get_income_stats
)
from datetime import datetime, timezone
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
    return render_template('index.html')

# --- Admin Routes ---

@bp.route('/admin')
@login_required
def admin_dashboard():
    # Fetch Analytics from MikroTik
    system_stats = get_mikrotik_system_stats()
    active_users = get_mikrotik_active_hotspot_users()
    traffic = get_mikrotik_interface_traffic()
    income_stats = get_income_stats()
    
    admins = Admin.query.all()

    return render_template('admin.html', 
                           system_stats=system_stats,
                           active_users=active_users,
                           traffic=traffic,
                           income_stats=income_stats,
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
    else:
        flash("Password cannot be empty.", "error")
    return redirect(url_for('main.admin_settings'))
