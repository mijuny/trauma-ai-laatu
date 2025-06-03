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
            
            # Add missing columns to studies table
            db.session.execute(text("""
                ALTER TABLE studies 
                ADD COLUMN IF NOT EXISTS patient_id VARCHAR(50)
            """))
            
            db.session.execute(text("""
                ALTER TABLE studies 
                ADD COLUMN IF NOT EXISTS patient_dob VARCHAR(10)
            """))
            
            db.session.execute(text("""
                ALTER TABLE studies 
                ADD COLUMN IF NOT EXISTS patient_gender VARCHAR(1)
            """))
            
            db.session.execute(text("""
                ALTER TABLE studies 
                ADD COLUMN IF NOT EXISTS study_uid VARCHAR(200)
            """))
            
            db.session.commit()
            print("Database migration completed successfully!")
        except Exception as e:
            db.session.rollback()
            print(f"Error during migration: {e}")
            raise

def add_comments_table():
    with db.engine.connect() as conn:
        conn.execute(text('''
            CREATE TABLE IF NOT EXISTS comments (
                id SERIAL PRIMARY KEY,
                study_id INTEGER REFERENCES studies(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        '''))

if __name__ == '__main__':
    with app.app_context():
        migrate_database()
        add_comments_table() 