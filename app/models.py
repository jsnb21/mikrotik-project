from . import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timezone, timedelta
import secrets
import string

class Admin(UserMixin, db.Model):
    __tablename__ = 'admins'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

class Voucher(db.Model):
    __tablename__ = 'vouchers'


    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    # duration_days matches the schema provided, but using Float to support hours/minutes
    duration_days = db.Column(db.Float, nullable=False) 
    # data_limit_gb matches schema
    data_limit_gb = db.Column(db.Float, nullable=False)
    # price matches schema
    price = db.Column(db.Float, nullable=False)
    # status: unused, active, expired
    status = db.Column(db.String(20), default='unused') 
    
    mac_address = db.Column(db.String(17), nullable=True) # Renamed from user_mac_address to match schema
    activated_at = db.Column(db.DateTime, nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)
    
    is_developer = db.Column(db.Boolean, default=False)

    @property
    def is_activated(self):
        return self.status == 'active'

    @property
    def duration(self):
        # Compatibility property if needed, returning seconds
        return int(self.duration_days * 86400)
        
    @property
    def remaining_seconds(self):
        if self.status != 'active' or not self.expiry_date:
            return 0
        now = datetime.now()
        rem = (self.expiry_date - now).total_seconds()
        return max(0, int(rem))
        
    # Compatibility Aliases for legacy code
    @property
    def user_mac_address(self):
        return self.mac_address

    @user_mac_address.setter
    def user_mac_address(self, value):
        self.mac_address = value

    @property
    def expires_at(self):
        return self.expiry_date

    @expires_at.setter
    def expires_at(self, value):
        self.expiry_date = value


    @property
    def remaining_seconds(self):
        """Returns remaining seconds if activated, or total duration if not."""
        if not self.is_activated:
            return self.duration
        
        # Developer codes never expire
        if self.is_developer:
            return 999999999  # Very large number to indicate infinite
        
        now = datetime.now(timezone.utc)
        if self.expires_at:
            # Ensure expires_at is timezone-aware (SQLite stores datetimes naively)
            expires_at = self.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if now < expires_at:
                return int((expires_at - now).total_seconds())
        return 0

    def activate(self, mac_address):
        if not self.is_activated:
            self.activated_at = datetime.now(timezone.utc)
            self.expires_at = self.activated_at + timedelta(seconds=self.duration)
            self.user_mac_address = mac_address
