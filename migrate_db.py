from app import app, db
from models import Study, Classification, User
from sqlalchemy import text

def migrate_database():
    with app.app_context():
        try:
            # Add classification_type column to classifications table
            db.session.execute(text("""
                ALTER TABLE classifications 
                ADD COLUMN IF NOT EXISTS classification_type VARCHAR(10) NOT NULL DEFAULT 'USER'
            """))
            
            db.session.commit()
            print("Database migration completed successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error during migration: {e}")
            raise

if __name__ == '__main__':
    migrate_database() 