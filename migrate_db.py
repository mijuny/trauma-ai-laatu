from app import app, db
from models import Study, Classification, User
from sqlalchemy import text

def migrate_database():
    with app.app_context():
        # Drop existing tables
        db.drop_all()
        
        # Create new tables with updated schema
        db.create_all()
        
        # Add new columns to studies table
        try:
            # Add patient_id column
            db.session.execute(text("""
                ALTER TABLE studies 
                ADD COLUMN IF NOT EXISTS patient_id VARCHAR(50)
            """))
            
            # Add patient_dob column
            db.session.execute(text("""
                ALTER TABLE studies 
                ADD COLUMN IF NOT EXISTS patient_dob VARCHAR(10)
            """))
            
            # Add patient_gender column with CHECK constraint
            db.session.execute(text("""
                ALTER TABLE studies 
                ADD COLUMN IF NOT EXISTS patient_gender VARCHAR(1) CHECK (patient_gender IN ('M', 'F'))
            """))
            
            # Add study_uid column
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

if __name__ == '__main__':
    migrate_database() 