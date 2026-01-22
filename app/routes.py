from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from . import db, login_manager
from .models import Admin, Voucher
from .utils import (
    get_mikrotik_system_stats, 
    get_mikrotik_active_hotspot_users, 
    get_mikrotik_interface_traffic,
    get_income_stats,
    mikrotik_allow_mac,
    get_mac_from_active_session
)
from datetime import datetime, timezone
import string
import secrets

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
        return redirect(url_for('admin.dashboard'))
    
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        print(f"Login attempt: username={username}")
        user = Admin.query.filter_by(username=username).first()
        print(f"User found: {user}")
        
        if user and user.check_password(password):
            print("Password check passed")
            login_user(user)
            return redirect(url_for('admin.dashboard'))
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
