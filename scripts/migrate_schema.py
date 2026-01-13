#!/usr/bin/env python3
"""
Migrate database schema to match current model.
Renames duration_minutes to duration (if needed) and adds is_developer column.
"""

import sys
import os
import sqlite3

def migrate():
    """Migrate database schema"""
    db_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'instance', 'pisonet.db')
    
    if not os.path.exists(db_path):
        print("❌ Database not found at:", db_path)
        return False
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check columns in vouchers table
        cursor.execute("PRAGMA table_info(vouchers)")
        columns = {col[1]: col for col in cursor.fetchall()}
        
        # Check if we need to rename duration_minutes to duration
        if 'duration_minutes' in columns and 'duration' not in columns:
            print("🔄 Renaming duration_minutes to duration...")
            cursor.execute("ALTER TABLE vouchers RENAME COLUMN duration_minutes TO duration")
            conn.commit()
            print("✅ Renamed duration_minutes to duration")
        
        # Refresh column info
        cursor.execute("PRAGMA table_info(vouchers)")
        columns = {col[1]: col for col in cursor.fetchall()}
        
        # Add is_developer column if it doesn't exist
        if 'is_developer' not in columns:
            print("🔄 Adding is_developer column...")
            cursor.execute("ALTER TABLE vouchers ADD COLUMN is_developer BOOLEAN DEFAULT 0")
            conn.commit()
            print("✅ Added is_developer column")
        else:
            print("✅ is_developer column already exists")
        
        print("\n✅ Migration complete!")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Migration error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    success = migrate()
    sys.exit(0 if success else 1)
