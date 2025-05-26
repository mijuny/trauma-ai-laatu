from app import app, db
from models import Study, Classification, User

def migrate_database():
    with app.app_context():
        # Drop existing tables
        db.drop_all()
        
        # Create new tables with updated schema
        db.create_all()
        
        print("Database migration completed successfully!")

if __name__ == '__main__':
    migrate_database() 