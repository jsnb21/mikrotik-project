import sys
import os
import sqlite3

# Ensure project root is on sys.path so we can import `config` when running
# this script from the `scripts/` directory.
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if proj_root not in sys.path:
    sys.path.insert(0, proj_root)

from config import Config
def ensure_duration_column(db_path):
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    cur.execute("PRAGMA table_info('vouchers')")
    cols = [r[1] for r in cur.fetchall()]
    if 'duration' in cols:
        print('`duration` column already exists in vouchers table.')
        conn.close()
        return

    print('Adding `duration` column to vouchers table (default 3600 seconds).')
    # Add column with default; existing rows receive the default value
    cur.execute("ALTER TABLE vouchers ADD COLUMN duration INTEGER DEFAULT 3600")
    conn.commit()
    conn.close()
    print('Done.')


if __name__ == '__main__':
    # Use same DB URL as app: default sqlite:///pisonet.db
    # Check common locations relative to the project root (not cwd)
    possible = [
        os.path.join(proj_root, 'instance', 'pisonet.db'),
        os.path.join(proj_root, 'pisonet.db'),
    ]

    checked = []
    for path in possible:
        checked.append(path)
        if os.path.exists(path):
            ensure_duration_column(path)
            break
    else:
        # Fallback: try to parse SQLALCHEMY_DATABASE_URI from Config
        uri = Config.SQLALCHEMY_DATABASE_URI
        if uri.startswith('sqlite:///'):
            dbpath = uri.replace('sqlite:///', '')
            checked.append(dbpath)
            if os.path.exists(dbpath):
                ensure_duration_column(dbpath)
            else:
                print('Database not found at', dbpath)
                print('Paths checked:')
                for p in checked:
                    print(' -', p)
        else:
            print('Unsupported DATABASE_URI; please run migration against your DB manually.')
