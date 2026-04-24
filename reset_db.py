from run import app
from app.core.extensions import db
from app.models.models import User

with app.app_context():
    print("Dropping all tables...")
    db.drop_all()
    print("Creating all tables...")
    db.create_all()
    
    # Re-seed
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', role='admin')
        admin.set_password('admin123')
        db.session.add(admin)
        
        petugas = User(username='petugas', role='petugas')
        petugas.set_password('petugas123')
        db.session.add(petugas)
        
        db.session.commit()
        print("Database reset and seeded successfully.")
    else:
        print("Admin already exists.")
