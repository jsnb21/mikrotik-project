import sqlite3
import os
import sys

code = sys.argv[1] if len(sys.argv) > 1 else '5GSD637C'
proj_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
db_paths = [
    os.path.join(proj_root, 'instance', 'pisonet.db'),
    os.path.join(proj_root, 'pisonet.db')
]

for p in db_paths:
    if os.path.exists(p):
        db = p
        break
else:
    print('No DB found in checked locations:')
    for p in db_paths:
        print(' -', p)
    sys.exit(2)

conn = sqlite3.connect(db)
conn.row_factory = sqlite3.Row
cur = conn.cursor()
cur.execute('SELECT * FROM vouchers WHERE code = ?', (code,))
row = cur.fetchone()
if not row:
    print(f'Voucher {code} not found in {db}')
    sys.exit(1)

print('Database:', db)
for k in row.keys():
    print(f'{k}: {row[k]}')

conn.close()
