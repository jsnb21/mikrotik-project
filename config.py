import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'hard-to-guess-string'
    
    # Database
    # Default to SQLite for local development, can be switched to PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///pisonet.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # MikroTik Settings
    MIKROTIK_HOST = os.environ.get('MIKROTIK_HOST') or '192.168.88.1'
    MIKROTIK_PORT = int(os.environ.get('MIKROTIK_PORT') or 8728)
    MIKROTIK_USER = os.environ.get('MIKROTIK_USER') or 'admin'
    MIKROTIK_PASSWORD = os.environ.get('MIKROTIK_PASSWORD') or ''
    MIKROTIK_USE_SSL = os.environ.get('MIKROTIK_USE_SSL', 'False').lower() == 'true'
    MIKROTIK_WAN_INTERFACE = os.environ.get('MIKROTIK_WAN_INTERFACE') or 'ether1'
