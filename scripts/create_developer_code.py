#!/usr/bin/env python3
"""
Create a developer voucher code that doesn't expire.
Usage: python scripts/create_developer_code.py
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import db, create_app
from app.models import Voucher
import string
import secrets

def generate_code():
    """Generate a random code"""
    chars = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(chars) for _ in range(8))

def create_developer_code(code=None):
    """Create a developer voucher code"""
    app = create_app()
    
    with app.app_context():
        if not code:
            code = generate_code()
        
        # Check if code already exists
        existing = Voucher.query.filter_by(code=code).first()
        if existing:
            print(f"Code {code} already exists!")
            return False
        
        # Create developer voucher with infinite duration
        voucher = Voucher(
            code=code,
            duration=999999999,  # Very long duration
            is_developer=True
        )
        
        db.session.add(voucher)
        db.session.commit()
        
        print(f"Developer code created: {code}")
        print(f"   Duration: Unlimited (∞)")
        print(f"   Type: Developer/Test Code")
        print(f"\n   Use this code to test the system.")
        print(f"   After activation, you can use 'End Session' to reset it.")
        
        return True

if __name__ == '__main__':
    # Create a default developer code
    create_developer_code('DEVTEST')
    
    # Or specify a custom code
    if len(sys.argv) > 1:
        create_developer_code(sys.argv[1])
