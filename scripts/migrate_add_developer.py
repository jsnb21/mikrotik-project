#!/usr/bin/env python3
"""
Migrate database to add is_developer column to vouchers table.
"""

import sys
import os
import sqlite3

def migrate():
    """Add is_developer column to vouchers table"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'pisonet.db')
    
    if not os.path.exists(db_path):
        print("Database not found at:", db_path)
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check if column exists
        cursor.execute("PRAGMA table_info(vouchers)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_developer' in columns:
            print("Column 'is_developer' already exists")
            conn.close()
            return True
        
        # Add the column
        cursor.execute("ALTER TABLE vouchers ADD COLUMN is_developer BOOLEAN DEFAULT 0")
        conn.commit()
        
        print("Added 'is_developer' column to vouchers table")
        conn.close()
        return True
        
    except Exception as e:
        print(f"Migration error: {str(e)}")
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
