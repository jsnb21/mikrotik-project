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
    duration = db.Column(db.Integer, nullable=False) # Duration in seconds (e.g., 3600 for 1 hour)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Activation details
    activated_at = db.Column(db.DateTime, nullable=True)
    expires_at = db.Column(db.DateTime, nullable=True)
    user_mac_address = db.Column(db.String(17), nullable=True)

    @property
    def is_activated(self):
        return self.activated_at is not None

    @property
    def remaining_seconds(self):
        """Returns remaining seconds if activated, or total duration if not."""
        if not self.is_activated:
            return self.duration
        
        now = datetime.now(timezone.utc)
        if self.expires_at and now < self.expires_at:
            return int((self.expires_at - now).total_seconds())
        return 0

    def activate(self, mac_address):
        if not self.is_activated:
            self.activated_at = datetime.now(timezone.utc)
            self.expires_at = self.activated_at + timedelta(seconds=self.duration)
            self.user_mac_address = mac_address
