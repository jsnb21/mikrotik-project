from flask import Blueprint

client_bp = Blueprint('client', __name__, template_folder='templates')

from . import routes
