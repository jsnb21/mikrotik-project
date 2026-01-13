from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login'

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    
    # Allow requests from your domain and local IP
    app.config['SERVER_NAME'] = None  # Don't enforce SERVER_NAME, allow all hosts
    app.config['TRUSTED_HOSTS'] = ['192.168.88.254', 'neuronet.ai', '*.neuronet.ai']

    db.init_app(app)
    login_manager.init_app(app)

    with app.app_context():
        from .models import Admin, Voucher  # Import models so db.create_all() works
        db.create_all()

    # Register Blueprint
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    return app
