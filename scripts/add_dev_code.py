#!/usr/bin/env python3
"""
Create a developer voucher code directly in the database.
"""

import sqlite3
import os
from datetime import datetime, timezone

def create_dev_code():
    """Create developer code directly in database"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'pisonet.db')
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # First, check the actual schema
        cursor.execute("PRAGMA table_info(vouchers)")
        columns = {col[1]: col[2] for col in cursor.fetchall()}
        print("Database columns:", list(columns.keys()))
        
        # Check if is_developer exists
        if 'is_developer' not in columns:
            print("\n🔄 Adding is_developer column...")
            cursor.execute("ALTER TABLE vouchers ADD COLUMN is_developer BOOLEAN DEFAULT 0")
            conn.commit()
            print("✅ Added is_developer column")
        
        # Determine which duration column to use
        duration_col = 'duration' if 'duration' in columns else 'duration_minutes'
        
        # Insert the developer code
        now = datetime.now(timezone.utc).isoformat()
        
        # Both duration and duration_minutes need to be provided
        sql = """
            INSERT INTO vouchers (code, duration_minutes, duration, price_amount, is_activated, created_at, is_developer)
            VALUES (?, ?, ?, ?, ?, ?, 1)
        """
        
        cursor.execute(sql, ('DEVTEST', 999999999, 999999999, 0, 0, now))
        conn.commit()
        
        print(f"\n✅ Developer code created!")
        print(f"   Code: DEVTEST")
        print(f"   Duration: Unlimited")
        print(f"   Type: Developer (never expires)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    create_dev_code()
