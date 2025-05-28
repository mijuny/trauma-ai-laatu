from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import JSON
import pytz

db = SQLAlchemy()

# Set Finnish timezone
FINNISH_TZ = pytz.timezone('Europe/Helsinki')

def get_finnish_time():
    """Get current time in Finnish timezone."""
    return datetime.now(FINNISH_TZ)

class User(db.Model):
    """Model for storing usernames."""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=get_finnish_time)
    
    # Relationship with classifications
    classifications = db.relationship('Classification', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.username}>'

class Study(db.Model):
    """Model for storing study information from HL7 messages."""
    __tablename__ = 'studies'
    
    id = db.Column(db.Integer, primary_key=True)
    accession_number = db.Column(db.String(50), unique=True, nullable=False)
    study_description = db.Column(db.String(200), nullable=False)
    raw_hl7 = db.Column(db.Text, nullable=False)
    parsed_data = db.Column(db.JSON)  # Store parsed data including raw_result
    ai_classification = db.Column(db.String(10), nullable=False)  # TP, TN, FP, FN
    created_at = db.Column(db.DateTime, default=get_finnish_time)
    
    # Additional fields from BoneView HL7 message
    patient_id = db.Column(db.String(50))
    patient_dob = db.Column(db.String(10))
    patient_gender = db.Column(db.String(1))
    study_uid = db.Column(db.String(200))
    
    # Relationship with classifications
    classifications = db.relationship('Classification', backref='study', lazy=True)

    def __repr__(self):
        return f'<Study {self.accession_number}>'

class Classification(db.Model):
    """Model for storing user classifications of studies."""
    __tablename__ = 'classifications'
    
    id = db.Column(db.Integer, primary_key=True)
    study_id = db.Column(db.Integer, db.ForeignKey('studies.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    classification = db.Column(db.String(10), nullable=False)  # TP, TN, FP, FN
    created_at = db.Column(db.DateTime, default=get_finnish_time)

    def __repr__(self):
        return f'<Classification {self.classification}>' 