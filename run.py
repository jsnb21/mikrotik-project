from app import create_app, db
from app.models import Voucher

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Voucher': Voucher}

# Add before request hook to handle any Host header issues
@app.before_request
def handle_host_header():
    """Allow requests from any host/domain"""
    pass

if __name__ == '__main__':
    # Initial setup for demo purposes: Create DB on first run if it doesn't exist
    with app.app_context():
        db.create_all()
<<<<<<< Updated upstream
        
    app.run(debug=True, port=5000)
=======
    
    # Run on 0.0.0.0 to be accessible from hotspot network
    # This allows access via IP (192.168.88.254) and domain (neuronet.ai)
    app.run(debug=True, host='0.0.0.0', port=5000, threaded=True)
>>>>>>> Stashed changes
