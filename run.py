from app import create_app, db
from app.models import Admin

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'Admin': Admin}

if __name__ == '__main__':
    # Initial setup for demo purposes: Create DB on first run if it doesn't exist
    with app.app_context():
        db.create_all()
        
    app.run(debug=True, port=5000)
