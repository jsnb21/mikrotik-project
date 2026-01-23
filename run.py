import os

from app import create_app, db
from app.models import Admin

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Admin': Admin}

# Add before request hook to handle any Host header issues
@app.before_request
def handle_host_header():
    """Allow requests from any host/domain"""
    pass

if __name__ == '__main__':
    # Initial setup for demo purposes: Create DB on first run if it doesn't exist
    with app.app_context():
        db.create_all()

    host = os.environ.get('FLASK_RUN_HOST', '0.0.0.0')
    port = int(os.environ.get('FLASK_RUN_PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', '0') == '1'

    if debug:
        # Debug mode for local development
        app.run(debug=True, host=host, port=port, threaded=True)
    else:
        # Production serving with Waitress (Windows-friendly WSGI server)
        from waitress import serve

        threads = int(os.environ.get('WAITRESS_THREADS', 8))
        serve(app, host=host, port=port, threads=threads)
