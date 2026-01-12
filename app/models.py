from . import db
from datetime import datetime, timezone, timedelta
import secrets
import string

class Voucher(db.Model):
    __tablename__ = 'vouchers'

    id = db.Column(db.Integer, primary_key=True)
    # The actual code user types in. Indexed for speed.
    code = db.Column(db.String(12), unique=True, index=True, nullable=False)
    
    # 30, 60, 300 minutes, etc.
    duration_minutes = db.Column(db.Integer, nullable=False)
    
    # Price at time of generation (for revenue analytics)
    price_amount = db.Column(db.Numeric(10, 2), nullable=False)
    
    # Status tracking
    is_activated = db.Column(db.Boolean, default=False, nullable=False)
    
    # Time tracking (Timezone aware)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    activated_at = db.Column(db.DateTime(timezone=True), nullable=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    
    # Audit trail
    user_mac_address = db.Column(db.String(17), nullable=True)

    def activate(self, mac_address):
        """Activates the voucher and calculates expiry."""
        if self.is_activated:
            raise ValueError("Voucher already used.")
        
        now = datetime.now(timezone.utc)
        self.is_activated = True
        self.activated_at = now
        self.expires_at = now + timedelta(minutes=self.duration_minutes)
        self.user_mac_address = mac_address
        # Note: db.session.commit() should be called by the caller

    @property
    def remaining_seconds(self):
        """Returns remaining seconds or 0 if expired."""
        if not self.is_activated or not self.expires_at:
            # If not activated, it technically has full duration remaining, 
            # but usually this property is used for active sessions.
            return self.duration_minutes * 60
        
        # Ensure we compare timezone-aware datetimes
        now = datetime.now(timezone.utc)
        if now > self.expires_at:
            return 0
            
        remaining = (self.expires_at - now).total_seconds()
        return max(0, int(remaining))

    @staticmethod
    def generate_code(length=8):
        """Generates a secure, uppercase alphanumeric code."""
        alphabet = string.ascii_uppercase + string.digits
        # Exclude confusing chars like I, O, 1, 0, Q
        safe_alphabet = ''.join(c for c in alphabet if c not in 'IO10Q')
        return ''.join(secrets.choice(safe_alphabet) for _ in range(length))
