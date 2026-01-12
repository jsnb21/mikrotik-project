from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config

db = SQLAlchemy()

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    with app.app_context():
        from .models import Voucher  # Import models so db.create_all() works
        db.create_all()

    # Register Blueprint
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    return app
