import os
import socket
import sys
from pathlib import Path

# Ensure project root is on sys.path for config import
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

print("=== ENV ===")
print("MIKROTIK_HOST:", os.getenv('MIKROTIK_HOST'))
print("MIKROTIK_USER:", os.getenv('MIKROTIK_USER'))
print("MIKROTIK_USERNAME:", os.getenv('MIKROTIK_USERNAME'))
print("MIKROTIK_PASSWORD length:", len(os.getenv('MIKROTIK_PASSWORD') or ''))
print("MIKROTIK_PORT:", os.getenv('MIKROTIK_PORT'))
print("MIKROTIK_USE_SSL:", os.getenv('MIKROTIK_USE_SSL'))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass
from config import Config
cfg = Config()
print("\n=== CONFIG ===")
print("HOST:", cfg.MIKROTIK_HOST)
print("USER:", cfg.MIKROTIK_USER)
print("PASSWORD length:", len(cfg.MIKROTIK_PASSWORD or ''))
print("PORT:", cfg.MIKROTIK_PORT)
print("USE_SSL:", cfg.MIKROTIK_USE_SSL)

host = cfg.MIKROTIK_HOST or os.getenv('MIKROTIK_HOST') or '192.168.88.1'
user = (os.getenv('MIKROTIK_USERNAME') or os.getenv('MIKROTIK_USER') or getattr(cfg, 'MIKROTIK_USERNAME', None) or cfg.MIKROTIK_USER or 'admin')
password = (os.getenv('MIKROTIK_PASSWORD') or cfg.MIKROTIK_PASSWORD or '')
port = int(os.getenv('MIKROTIK_PORT') or cfg.MIKROTIK_PORT or 8728)
use_ssl = (os.getenv('MIKROTIK_USE_SSL') or str(cfg.MIKROTIK_USE_SSL)).lower() == 'true'

print("\n=== USING ===")
print("HOST:", host)
print("USER:", user)
print("PASSWORD length:", len(password))
print("PORT:", port)
print("USE_SSL:", use_ssl)

print("\n=== TCP CHECK ===")
try:
    s = socket.socket()
    s.settimeout(2.0)
    s.connect((host, port))
    print("TCP port reachable:", host, port)
    s.close()
except Exception as e:
    print("TCP connect failed:", e.__class__.__name__, str(e))

print("\n=== API CHECK ===")
try:
    from routeros_api import RouterOsApiPool
    print("routeros_api import: OK")
    try:
        api_pool = RouterOsApiPool(host, username=user.strip(), password=password.strip(), port=port, use_ssl=use_ssl, plaintext_login=True)
        api = api_pool.get_api()
        res = api.get_resource('/system/resource').get()
        print("API connected; sample resource:", res[:1])
        api_pool.disconnect()
    except Exception as e:
        print("API connection failed:", e.__class__.__name__, str(e))
except Exception as e:
    print("routeros_api import FAILED:", e.__class__.__name__, str(e))
