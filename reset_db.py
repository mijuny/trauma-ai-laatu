from app import app, db
import os

def reset_db():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        print("All tables dropped.")
        
        # Create all tables
        db.create_all()
        print("Database tables recreated successfully!")
        
        # Reset accession counter
        with open('accession_counter.txt', 'w') as f:
            f.write('0')
        print("Accession counter reset to 0.")

if __name__ == '__main__':
    reset_db() 