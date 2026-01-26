#!/usr/bin/env python3
"""
Remove duplicate duration_minutes column from vouchers table.
Keeps the duration column which has the same data.
"""

import sys
import os
import sqlite3

def cleanup_duration_columns():
    """Remove duration_minutes column"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'pisonet.db')
    
    if not os.path.exists(db_path):
        print(f"Database not found at: {db_path}")
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current schema
        cursor.execute("PRAGMA table_info(vouchers)")
        columns = {col[1]: col for col in cursor.fetchall()}
        col_names = list(columns.keys())
        
        print(f"Current columns: {col_names}")
        
        if 'duration_minutes' not in columns:
            print("duration_minutes column does not exist, nothing to remove")
            return True
        
        # Rename old table
        cursor.execute("ALTER TABLE vouchers RENAME TO vouchers_old")
        
        # Recreate table without duration_minutes
        cursor.execute("""
            CREATE TABLE vouchers (
                id INTEGER PRIMARY KEY,
                code TEXT UNIQUE NOT NULL,
                duration INTEGER NOT NULL,
                created_at DATETIME,
                activated_at DATETIME,
                expires_at DATETIME,
                user_mac_address TEXT,
                is_developer BOOLEAN DEFAULT 0
            )
        """)
        
        # Copy all data back (only the columns we want)
        cursor.execute("""
            INSERT INTO vouchers 
            (id, code, duration, created_at, activated_at, expires_at, user_mac_address, is_developer)
            SELECT 
            id, code, duration, created_at, activated_at, expires_at, user_mac_address, is_developer
            FROM vouchers_old
        """)
        
        # Drop old table
        cursor.execute("DROP TABLE vouchers_old")
        
        conn.commit()
        print("Removed duration_minutes column")
        
        # Verify final schema
        cursor.execute("PRAGMA table_info(vouchers)")
        final_columns = {col[1]: col for col in cursor.fetchall()}
        print(f"Final columns: {list(final_columns.keys())}")
        
        cursor.execute("SELECT COUNT(*) FROM vouchers")
        total = cursor.fetchone()[0]
        print(f"Total vouchers in database: {total}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = cleanup_duration_columns()
    sys.exit(0 if success else 1)
