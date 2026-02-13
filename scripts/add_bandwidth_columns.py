#!/usr/bin/env python3
"""
Migration script to add bandwidth rate limit columns to vouchers table
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db
from sqlalchemy import text

def migrate():
    app = create_app()
    
    with app.app_context():
        try:
            # Check if columns already exist
            result = db.session.execute(text("PRAGMA table_info(vouchers)"))
            columns = [row[1] for row in result]
            
            changes_made = False
            
            # Add rate_limit_up column if not exists
            if 'rate_limit_up' not in columns:
                print("Adding rate_limit_up column...")
                db.session.execute(text("ALTER TABLE vouchers ADD COLUMN rate_limit_up VARCHAR(20) DEFAULT '1M'"))
                changes_made = True
            else:
                print("rate_limit_up column already exists")
            
            # Add rate_limit_down column if not exists
            if 'rate_limit_down' not in columns:
                print("Adding rate_limit_down column...")
                db.session.execute(text("ALTER TABLE vouchers ADD COLUMN rate_limit_down VARCHAR(20) DEFAULT '2M'"))
                changes_made = True
            else:
                print("rate_limit_down column already exists")
            
            if changes_made:
                db.session.commit()
                print("✅ Migration completed successfully!")
            else:
                print("✅ No migration needed - columns already exist")
                
        except Exception as e:
            print(f"❌ Migration failed: {e}")
            db.session.rollback()
            sys.exit(1)

if __name__ == '__main__':
    migrate()
