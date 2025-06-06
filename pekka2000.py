import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_file, session, redirect
from flask_sqlalchemy import SQLAlchemy
from models import db, Study, Classification, User, Comment
import hl7
import csv
from io import StringIO
from dateutil import parser
from dotenv import load_dotenv
from translations import TRANSLATIONS
import pytz

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://localhost/radiology_ai')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev')

# Set Finnish timezone
FINNISH_TZ = pytz.timezone('Europe/Helsinki')

db.init_app(app)

def get_finnish_time():
    """Get current time in Finnish timezone."""
    return datetime.now(FINNISH_TZ)

def convert_to_finnish_time(dt):
    """Convert a datetime object to Finnish timezone."""
    if dt.tzinfo is None:
        # If no timezone info, assume it's UTC
        dt = pytz.UTC.localize(dt)
    elif dt.tzinfo == FINNISH_TZ:
        # If already in Finnish time, return as is
        return dt
    # Convert to Finnish time
    return dt.astimezone(FINNISH_TZ)

def get_translation(key, lang='fi'):
    """Get translation for a given key in the specified language."""
    return TRANSLATIONS.get(lang, TRANSLATIONS['fi']).get(key, key)

@app.context_processor
def inject_translations():
    """Inject translations into all templates."""
    lang = session.get('lang', 'fi')
    
    # Create a translation function that uses the session language
    def t(key):
        return get_translation(key, lang)
    
    return dict(t=t, lang=lang, min=min, max=max, convert_to_finnish_time=convert_to_finnish_time)

@app.route('/set_language/<lang>')
def set_language(lang):
    """Set the language preference."""
    if lang in TRANSLATIONS:
        session['lang'] = lang
    return redirect(request.referrer or '/')

def parse_hl7_message(message):
    """Parse HL7 message and extract relevant information."""
    try:
        # Print raw message for debugging
        print("\nRaw HL7 message received:")
        print("-" * 50)
        print(message)
        print("-" * 50)
        
        # Ensure message has proper line endings
        if '\n' in message and '\r' not in message:
            message = message.replace('\n', '\r')
        
        # Parse the message
        h = hl7.parse(message)
        
        # Print all segments for debugging
        for segment_id in ['MSH', 'PID', 'OBR', 'OBX', 'ZDS']:
            segment = h.segment(segment_id)
            if segment:
                print(f"Segment {segment_id}: {segment}")
                # Print detailed segment structure
                for i, field in enumerate(segment):
                    print(f"  Field {i}: {field}")
        
        # Extract fields from the message
        try:
            # Get MSH segment
            msh_segment = h.segment('MSH')
            print("\nMSH segment:", msh_segment)
            
            # Parse timestamp from MSH segment
            study_time = None
            if msh_segment and len(msh_segment) > 7:
                try:
                    # Get timestamp from MSH-7 (index 7)
                    timestamp_str = str(msh_segment[7][0])
                    print(f"Raw timestamp from MSH: {timestamp_str}")
                    
                    # Handle timestamp with milliseconds (YYYYMMDDHHMMSS.SSS)
                    if '.' in timestamp_str:
                        timestamp_str = timestamp_str.split('.')[0]  # Remove milliseconds
                    
                    # Parse the timestamp (format: YYYYMMDDHHMMSS)
                    year = int(timestamp_str[0:4])
                    month = int(timestamp_str[4:6])
                    day = int(timestamp_str[6:8])
                    hour = int(timestamp_str[8:10])
                    minute = int(timestamp_str[10:12])
                    second = int(timestamp_str[12:14])
                    
                    # Create datetime object in UTC (assuming HL7 timestamp is in UTC)
                    study_time = datetime(year, month, day, hour, minute, second)
                    # Convert to Finnish timezone
                    study_time = convert_to_finnish_time(study_time)
                    print(f"Study time (Finnish): {study_time}")
                except (IndexError, ValueError) as e:
                    print(f"Error parsing timestamp from MSH segment: {e}")
                    study_time = get_finnish_time()  # Fallback to current Finnish time
            
            # Get PID segment
            pid_segment = h.segment('PID')
            print("PID segment:", pid_segment)
            
            # Get OBR segment
            obr_segment = h.segment('OBR')
            print("OBR segment:", obr_segment)
            
            # Get OBX segment
            obx_segment = h.segment('OBX')
            print("OBX segment:", obx_segment)
            
            # Get ZDS segment if available
            zds_segment = h.segment('ZDS')
            print("ZDS segment:", zds_segment)
            if zds_segment:
                print("ZDS segment fields:")
                for i, field in enumerate(zds_segment):
                    print(f"  ZDS[{i}]: {field}")
            
            # Extract fields with proper error handling
            # Try different possible positions for accession number
            accession_number = None
            if len(obr_segment) > 3 and obr_segment[3][0]:  # Try OBR-3 first
                accession_number = str(obr_segment[3][0])
            elif len(obr_segment) > 2 and obr_segment[2][0]:  # Then try OBR-2
                accession_number = str(obr_segment[2][0])
            
            # Clean up study description (remove ^ prefix if present)
            study_description = str(obr_segment[4][0]) if len(obr_segment) > 4 else None
            if study_description and study_description.startswith('^'):
                study_description = study_description[1:]
            
            # Get result from OBX
            result = str(obx_segment[5][0]).upper() if len(obx_segment) > 5 else None
            
            # Extract additional fields
            patient_id = str(pid_segment[2][0]) if len(pid_segment) > 2 else None
            patient_dob = str(pid_segment[7][0]) if len(pid_segment) > 7 else None
            patient_gender = str(pid_segment[8][0]) if len(pid_segment) > 8 else None
            
            # Get study UID from ZDS segment - first component before the first ^
            study_uid = None
            if zds_segment and len(zds_segment) > 1:  # Changed from > 0 to > 1
                try:
                    # Print raw ZDS value for debugging
                    print(f"\nRaw ZDS value: {zds_segment[1]}")  # Changed from [0] to [1]
                    zds_value = str(zds_segment[1][0])  # Changed from [0] to [1]
                    print(f"ZDS value after str conversion: {zds_value}")
                    if '^' in zds_value:
                        study_uid = zds_value.split('^')[0]
                        print(f"Study UID after splitting: {study_uid}")
                    else:
                        study_uid = zds_value
                except (IndexError, AttributeError) as e:
                    print(f"Error extracting study UID from ZDS segment: {e}")
                    study_uid = None
            
            # Validate patient gender
            if not patient_gender or patient_gender not in ['M', 'F']:
                patient_gender = 'M'  # Default to 'M' if invalid
            
            print(f"\nExtracted fields:")
            print(f"Accession: {accession_number}")
            print(f"Description: {study_description}")
            print(f"Result: {result}")
            print(f"Patient ID: {patient_id}")
            print(f"Patient DOB: {patient_dob}")
            print(f"Patient Gender: {patient_gender}")
            print(f"Study UID: {study_uid}")
            print(f"Study Time: {study_time}")
            
            if not all([accession_number, study_description, result]):
                missing_fields = []
                if not accession_number: missing_fields.append("accession_number")
                if not study_description: missing_fields.append("study_description")
                if not result: missing_fields.append("result")
                print(f"Missing required fields: {', '.join(missing_fields)}")
                return None
            
            # Store the result as is, including DOUBT
            if result not in ['POSITIVE', 'NEGATIVE', 'DOUBT']:
                print(f"Warning: Unknown result value '{result}', defaulting to NEGATIVE")
                result = 'NEGATIVE'
            
            # Convert study_time to string for JSON serialization
            study_time_str = study_time.isoformat() if study_time else None
            
            return {
                'accession_number': accession_number,
                'study_description': study_description,
                'ai_classification': result,
                'raw_result': result,
                'patient_id': patient_id,
                'patient_dob': patient_dob,
                'patient_gender': patient_gender,
                'study_uid': study_uid,
                'study_time': study_time_str
            }
            
        except IndexError as e:
            print(f"Error accessing HL7 segment fields: {e}")
            return None
            
    except Exception as e:
        print(f"Error parsing HL7 message: {e}")
        print(f"Message content: {message}")
        return None

@app.route('/api/hl7', methods=['POST'])
def receive_hl7():
    """Receive and process HL7 messages."""
    if request.method == 'POST':
        try:
            message = request.data.decode('utf-8')
            print(f"Received HL7 message: {message}")
            
            # Ensure message has proper line endings
            if '\n' in message and '\r' not in message:
                message = message.replace('\n', '\r')
            
            try:
                h = hl7.parse(message)
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': 'Failed to parse HL7 message',
                    'error': str(e),
                    'raw_message': message
                }), 400
            
            try:
                # Get MSH segment
                msh_segment = h.segment('MSH')
                if not msh_segment:
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing MSH segment',
                        'raw_message': message
                    }), 400
                
                # Parse timestamp from MSH segment
                study_time = None
                if len(msh_segment) > 7:
                    try:
                        # Get timestamp from MSH-7 (index 7)
                        timestamp_str = str(msh_segment[7][0])
                        print(f"Raw timestamp from MSH: {timestamp_str}")
                        
                        # Handle timestamp with milliseconds (YYYYMMDDHHMMSS.SSS)
                        if '.' in timestamp_str:
                            timestamp_str = timestamp_str.split('.')[0]  # Remove milliseconds
                        
                        # Parse the timestamp (format: YYYYMMDDHHMMSS)
                        year = int(timestamp_str[0:4])
                        month = int(timestamp_str[4:6])
                        day = int(timestamp_str[6:8])
                        hour = int(timestamp_str[8:10])
                        minute = int(timestamp_str[10:12])
                        second = int(timestamp_str[12:14])
                        
                        # Create datetime object in UTC (assuming HL7 timestamp is in UTC)
                        study_time = datetime(year, month, day, hour, minute, second)
                        # Convert to Finnish timezone
                        study_time = convert_to_finnish_time(study_time)
                        print(f"Study time (Finnish): {study_time}")
                    except (IndexError, ValueError) as e:
                        print(f"Error parsing timestamp from MSH segment: {e}")
                        study_time = get_finnish_time()  # Fallback to current Finnish time
                
                # Get PID segment
                pid_segment = h.segment('PID')
                if not pid_segment:
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing PID segment',
                        'raw_message': message
                    }), 400
                
                # Get OBR segment
                obr_segment = h.segment('OBR')
                if not obr_segment:
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing OBR segment',
                        'raw_message': message
                    }), 400
                
                # Get OBX segment
                obx_segment = h.segment('OBX')
                if not obx_segment:
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing OBX segment',
                        'raw_message': message
                    }), 400
                
                # Extract fields with proper error handling
                try:
                    accession_number = str(obr_segment[3][0]) if len(obr_segment) > 3 and obr_segment[3][0] else str(obr_segment[2][0])
                except IndexError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing accession number in OBR segment',
                        'raw_message': message
                    }), 400
                
                try:
                    study_description = str(obr_segment[4][0])
                    # Remove ^ prefix if present
                    if study_description.startswith('^'):
                        study_description = study_description[1:]
                except IndexError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing study description in OBR segment',
                        'raw_message': message
                    }), 400
                
                try:
                    result = str(obx_segment[5][0]).upper()
                except IndexError:
                    return jsonify({
                        'status': 'error',
                        'message': 'Missing result in OBX segment',
                        'raw_message': message
                    }), 400
                
                # Store the result as is, including DOUBT
                if result not in ['POSITIVE', 'NEGATIVE', 'DOUBT']:
                    return jsonify({
                        'status': 'error',
                        'message': f'Invalid result value: {result}',
                        'raw_message': message
                    }), 400
                
                # Extract additional fields
                patient_id = str(pid_segment[2][0]) if len(pid_segment) > 2 else None
                patient_dob = str(pid_segment[7][0]) if len(pid_segment) > 7 else None
                patient_gender = str(pid_segment[8][0]) if len(pid_segment) > 8 else None
                
                # Get ZDS segment if available
                zds_segment = h.segment('ZDS')
                study_uid = None
                if zds_segment and len(zds_segment) > 1:
                    try:
                        zds_value = str(zds_segment[1][0])
                        if '^' in zds_value:
                            study_uid = zds_value.split('^')[0]
                        else:
                            study_uid = zds_value
                    except (IndexError, AttributeError) as e:
                        print(f"Error extracting study UID from ZDS segment: {e}")
                
                # Validate patient gender
                if not patient_gender or patient_gender not in ['M', 'F']:
                    patient_gender = 'M'  # Default to 'M' if invalid
                
                # Check if study already exists
                existing_study = Study.query.filter_by(accession_number=accession_number).first()
                if existing_study:
                    return jsonify({
                        'status': 'error',
                        'message': f'Study with accession number {accession_number} already exists'
                    }), 400
                
                # Create new study with Finnish time
                study = Study(
                    accession_number=accession_number,
                    study_description=study_description,
                    raw_hl7=message,
                    parsed_data={
                        'accession_number': accession_number,
                        'study_description': study_description,
                        'ai_classification': result,
                        'raw_result': result,
                        'patient_id': patient_id,
                        'patient_dob': patient_dob,
                        'patient_gender': patient_gender,
                        'study_uid': study_uid,
                        'study_time': study_time.isoformat() if study_time else None
                    },
                    ai_classification=result,
                    patient_id=patient_id,
                    patient_dob=patient_dob,
                    patient_gender=patient_gender,
                    study_uid=study_uid,
                    created_at=study_time or get_finnish_time()
                )
                print(f"\nDebug - Creating new study:")
                print(f"Study time from HL7: {study_time}")
                print(f"Current Finnish time: {get_finnish_time()}")
                print(f"Final created_at: {study.created_at}")
                
                db.session.add(study)
                db.session.commit()
                return jsonify({'status': 'success'}), 200
                
            except Exception as e:
                return jsonify({
                    'status': 'error',
                    'message': f'Error processing HL7 segments: {str(e)}',
                    'raw_message': message
                }), 400
            
        except Exception as e:
            return jsonify({
                'status': 'error',
                'message': f'Error processing message: {str(e)}',
                'raw_message': message if 'message' in locals() else None
            }), 500

@app.route('/api/username', methods=['POST'])
def add_username():
    """Add a new username."""
    data = request.json
    if not data or 'username' not in data:
        return jsonify({'error': 'Username is required'}), 400
    
    username = data['username'].strip()
    if not username:
        return jsonify({'error': 'Username cannot be empty'}), 400
    
    # Check if username already exists (case-insensitive)
    existing_user = User.query.filter(
        db.func.lower(User.username) == db.func.lower(username)
    ).first()
    
    if existing_user:
        return jsonify({'error': 'Username already exists'}), 400
    
    # Create new user
    user = User(username=username)
    db.session.add(user)
    db.session.commit()
    
    return jsonify({'status': 'success', 'username': username}), 200

@app.route('/api/classify', methods=['POST'])
def classify_study():
    """Classify a study."""
    data = request.json
    print("Received classify request:", data)
    if not all(k in data for k in ['study_id', 'username', 'classification', 'classification_type']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Handle classification removal
    if data['classification'] == 'REMOVE':
        # Get or create user
        username = data['username'].strip()
        if not username:
            return jsonify({'error': 'Username cannot be empty'}), 400
        user = User.query.filter(
            db.func.lower(User.username) == db.func.lower(username)
        ).first()
        if not user:
            return jsonify({'error': 'User not found'}), 404
        # Find and delete the classification (allow any user to remove any classification)
        classification = Classification.query.filter(
            Classification.study_id == data['study_id'],
            Classification.classification_type == data['classification_type']
        ).first()
        if classification:
            db.session.delete(classification)
            db.session.commit()
            return jsonify({'status': 'success'}), 200
        else:
            if data['classification_type'] == 'FOLLOW_UP':
                return jsonify({'error': 'Jatkotutkimuksella ei ole luokittelua'}), 404
            else:
                return jsonify({'error': 'Käyttäjällä ei ole luokittelua'}), 404
    
    # Validate classification value for new classifications
    valid_classifications = ['POSITIVE', 'NEGATIVE']
    if data['classification'] not in valid_classifications:
        return jsonify({'error': 'Invalid classification value'}), 400
    
    # Validate classification type
    valid_types = ['USER', 'FOLLOW_UP']
    if data['classification_type'] not in valid_types:
        return jsonify({'error': 'Invalid classification type'}), 400
    
    # Check if study exists
    study = db.session.get(Study, data['study_id'])
    if not study:
        return jsonify({'error': 'Study not found'}), 404
    
    # Get or create user
    username = data['username'].strip()
    if not username:
        return jsonify({'error': 'Username cannot be empty'}), 400
    
    user = User.query.filter(
        db.func.lower(User.username) == db.func.lower(username)
    ).first()
    
    if not user:
        user = User(username=username)
        db.session.add(user)
        db.session.flush()  # Get the user ID without committing
    
    # Get AI classification
    ai_classification = study.ai_classification

    # Convert AI classification to POSITIVE/NEGATIVE if it's TP/TN or DOUBT (for logic only)
    logic_ai_classification = ai_classification
    if logic_ai_classification in ['TP', 'FP']:
        logic_ai_classification = 'POSITIVE'
    elif logic_ai_classification in ['TN', 'FN']:
        logic_ai_classification = 'NEGATIVE'
    elif logic_ai_classification == 'DOUBT':
        logic_ai_classification = 'POSITIVE'

    # Get the classification value
    classification_value = data['classification']

    # Determine final classification based on classification type and rules
    if data['classification_type'] == 'FOLLOW_UP':
        # Follow-up classification rules
        if classification_value == 'POSITIVE' and logic_ai_classification == 'POSITIVE':
            final_classification = 'TP'
        elif classification_value == 'NEGATIVE' and logic_ai_classification == 'NEGATIVE':
            final_classification = 'TN'
        elif classification_value == 'POSITIVE' and logic_ai_classification == 'NEGATIVE':
            final_classification = 'FN'
        elif classification_value == 'NEGATIVE' and logic_ai_classification == 'POSITIVE':
            final_classification = 'FP'
        else:
            return jsonify({'error': 'Invalid follow-up classification logic'}), 400
    else:  # USER classification
        # User classification rules
        if classification_value == 'POSITIVE' and logic_ai_classification == 'POSITIVE':
            final_classification = 'TP'
        elif classification_value == 'NEGATIVE' and logic_ai_classification == 'NEGATIVE':
            final_classification = 'TN'
        elif classification_value == 'NEGATIVE' and (logic_ai_classification == 'POSITIVE' or logic_ai_classification == 'DOUBT'):
            final_classification = 'FP'
        elif classification_value == 'POSITIVE' and logic_ai_classification == 'NEGATIVE':
            final_classification = 'FN'
        else:
            return jsonify({'error': 'Invalid user classification logic'}), 400
    
    # Check for existing classification by the same user for this study and type
    existing_classification = Classification.query.filter(
        Classification.study_id == data['study_id'],
        Classification.user_id == user.id,
        Classification.classification_type == data['classification_type']
    ).first()
    
    if existing_classification:
        # Update existing classification
        existing_classification.classification = final_classification
        existing_classification.created_at = datetime.utcnow()
    else:
        # Create new classification
        classification = Classification(
            study_id=data['study_id'],
            user_id=user.id,
            classification=final_classification,
            classification_type=data['classification_type']
        )
        db.session.add(classification)
    
    db.session.commit()
    return jsonify({'status': 'success'}), 200

@app.route('/')
def index():
    """Main page showing studies and statistics."""
    # Get filter parameters
    time_filter = request.args.get('time_filter', 'all')
    study_type = request.args.get('study_type', '')
    result_type = request.args.get('result_type', '')  # This will be empty string when "Kaikki tulokset" is selected
    selected_username = request.args.get('username', '')
    page = request.args.get('page', 1, type=int)
    per_page = 100
    lang = session.get('lang', 'fi')
    
    # Base query for filtered studies (for display)
    query = Study.query
    
    # Apply time filter
    if time_filter != 'all':
        if time_filter == 'today':
            # Get start of today in Finnish timezone
            today_start = datetime.now(FINNISH_TZ).replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.filter(Study.created_at >= today_start)
        elif time_filter == 'week':
            week_start = datetime.now(FINNISH_TZ) - timedelta(days=7)
            query = query.filter(Study.created_at >= week_start)
        elif time_filter == 'month':
            month_start = datetime.now(FINNISH_TZ) - timedelta(days=30)
            query = query.filter(Study.created_at >= month_start)
    
    # Apply AC number filter
    if study_type:
        query = query.filter(Study.accession_number.ilike(f'%{study_type}%'))
    
    # Get all classifications for the selected username
    classifications_query = Classification.query
    if selected_username:
        classifications_query = classifications_query.join(User).filter(
            db.func.lower(User.username) == db.func.lower(selected_username)
        )
    user_classifications = classifications_query.all()
    
    # Create a mapping of study_id to user classification
    user_classification_map = {c.study_id: c.classification for c in user_classifications}
    
    # Filter studies based on result_type if specified
    if result_type and result_type.strip():  # Only apply filter if result_type is not empty
        if result_type == 'CLASSIFIED':
            # Get all study IDs that have any classification
            classified_study_ids = {c.study_id for c in user_classifications}
            if classified_study_ids:
                query = query.filter(Study.id.in_(classified_study_ids))
            else:
                query = query.filter(Study.id == None)  # No classified studies
        elif result_type == 'MY_CLASSIFIED':
            # Get study IDs that have been classified by the selected user
            if selected_username:
                my_classified_study_ids = {c.study_id for c in user_classifications}
                if my_classified_study_ids:
                    query = query.filter(Study.id.in_(my_classified_study_ids))
                else:
                    query = query.filter(Study.id == None)  # No classified studies
            else:
                query = query.filter(Study.id == None)  # No username selected
        else:
            # For specific result types (TP, TN, FP, FN, DOUBT)
            filtered_study_ids = set()
            
            # Get all studies that match the filter criteria
            all_studies = query.all()
            for study in all_studies:
                user_classification = user_classification_map.get(study.id)
                
                # If there's a user classification, use it
                if user_classification:
                    if user_classification == result_type:
                        filtered_study_ids.add(study.id)
                # If no user classification, check AI classification
                else:
                    # For TP filter, include studies with POSITIVE or DOUBT AI classification
                    if result_type == 'TP' and study.ai_classification in ['POSITIVE', 'DOUBT']:
                        filtered_study_ids.add(study.id)
                    # For TN filter, include studies with NEGATIVE AI classification
                    elif result_type == 'TN' and study.ai_classification == 'NEGATIVE':
                        filtered_study_ids.add(study.id)
                    # For DOUBT filter, include studies with DOUBT AI classification
                    elif result_type == 'DOUBT' and study.ai_classification == 'DOUBT':
                        filtered_study_ids.add(study.id)
                    # For FP and FN, only include if there's a user classification
                    elif result_type in ['FP', 'FN']:
                        continue
            
            # Apply the filtered study IDs to the query
            if filtered_study_ids:
                query = query.filter(Study.id.in_(filtered_study_ids))
            else:
                # If no studies match the filter, return empty result
                query = query.filter(Study.id == None)
    
    # Get filtered studies for display with pagination
    studies = query.order_by(Study.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
    # Get all studies for statistics (unfiltered)
    all_studies = Study.query.all()
    all_classifications = Classification.query.all()
    all_classification_map = {c.study_id: c.classification for c in all_classifications}
    
    # Get unique usernames
    usernames = db.session.query(User.username).distinct().all()
    usernames = [username[0] for username in usernames]
    
    # Calculate statistics from all studies
    total_studies = len(all_studies)
    total_classifications = len(all_classifications)
    
    # Count classifications by type
    tp_count = 0
    tn_count = 0
    fp_count = 0
    fn_count = 0
    
    for study in all_studies:
        # Get all classifications for this study
        study_classifications = [c for c in all_classifications if c.study_id == study.id]
        
        # Check for follow-up classification first
        follow_up_classification = next((c for c in study_classifications if c.classification_type == 'FOLLOW_UP'), None)
        
        if follow_up_classification:
            # Use follow-up classification
            if follow_up_classification.classification == 'TP':
                tp_count += 1
            elif follow_up_classification.classification == 'TN':
                tn_count += 1
            elif follow_up_classification.classification == 'FP':
                fp_count += 1
            elif follow_up_classification.classification == 'FN':
                fn_count += 1
        else:
            # No follow-up, use user classification if available
            user_classification = next((c for c in study_classifications if c.classification_type == 'USER'), None)
            
            if user_classification:
                # User has provided a classification
                if user_classification.classification == 'TP':
                    tp_count += 1
                elif user_classification.classification == 'TN':
                    tn_count += 1
                elif user_classification.classification == 'FP':
                    fp_count += 1
                elif user_classification.classification == 'FN':
                    fn_count += 1
            else:
                # No user classification - assume AI is correct
                # Treat DOUBT as POSITIVE for statistics
                if study.ai_classification in ['POSITIVE', 'DOUBT']:
                    tp_count += 1  # Assume True Positive
                else:  # ai_classification == 'NEGATIVE'
                    tn_count += 1  # Assume True Negative
    
    # Calculate metrics
    total_classified = tp_count + tn_count + fp_count + fn_count
    
    # Sensitivity (True Positive Rate)
    sensitivity = (tp_count / (tp_count + fn_count) * 100) if (tp_count + fn_count) > 0 else 0
    
    # Specificity (True Negative Rate)
    specificity = (tn_count / (tn_count + fp_count) * 100) if (tn_count + fp_count) > 0 else 0
    
    # Accuracy
    accuracy = ((tp_count + tn_count) / total_classified * 100) if total_classified > 0 else 0
    
    # Positive Predictive Value (PPV)
    ppv = (tp_count / (tp_count + fp_count) * 100) if (tp_count + fp_count) > 0 else 0
    
    # Negative Predictive Value (NPV)
    npv = (tn_count / (tn_count + fn_count) * 100) if (tn_count + fn_count) > 0 else 0
    
    # F1 Score
    f1_score = (2 * tp_count / (2 * tp_count + fp_count + fn_count) * 100) if (2 * tp_count + fp_count + fn_count) > 0 else 0
    
    return render_template('index.html',
                         studies=studies,
                         total_studies=total_studies,
                         total_classifications=total_classifications,
                         tp_count=tp_count,
                         tn_count=tn_count,
                         fp_count=fp_count,
                         fn_count=fn_count,
                         sensitivity=sensitivity,
                         specificity=specificity,
                         accuracy=accuracy,
                         ppv=ppv,
                         npv=npv,
                         f1_score=f1_score,
                         usernames=usernames,
                         selected_username=selected_username,
                         time_filter=time_filter,
                         study_type=study_type,
                         result_type=result_type,
                         page=page,
                         lang=lang,
                         finnish_tz=FINNISH_TZ)

@app.route('/reset_filters')
def reset_filters():
    """Reset all filters and redirect to the main page."""
    username = request.args.get('username', '')
    if username:
        return redirect(f'/?username={username}')
    return redirect('/')

@app.route('/api/comments', methods=['GET'])
def get_comments():
    study_id = request.args.get('study_id')
    if not study_id:
        return jsonify({'error': 'Missing study_id'}), 400
    
    try:
        study_id = int(study_id)  # Convert string to integer
    except ValueError:
        return jsonify({'error': 'Invalid study_id format'}), 400
    
    comments = Comment.query.filter_by(study_id=study_id).order_by(Comment.created_at.desc()).all()
    return jsonify([
        {
            'id': c.id,
            'user': c.user.username,
            'user_id': c.user_id,
            'text': c.text,
            'created_at': c.created_at.isoformat(),
            'updated_at': c.updated_at.isoformat() if c.updated_at else None
        } for c in comments
    ])

@app.route('/api/comments', methods=['POST'])
def add_comment():
    data = request.json
    if not all(k in data for k in ['study_id', 'username', 'text']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        study_id = int(data['study_id'])  # Convert string to integer
    except (ValueError, TypeError):
        return jsonify({'error': 'Invalid study_id format'}), 400
    
    user = User.query.filter(db.func.lower(User.username) == db.func.lower(data['username'])).first()
    if not user:
        user = User(username=data['username'])
        db.session.add(user)
        db.session.flush()
    comment = Comment(
        study_id=study_id,
        user_id=user.id,
        text=data['text']
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify({'status': 'success', 'id': comment.id}), 200

@app.route('/api/comments/<int:comment_id>', methods=['PUT'])
def edit_comment(comment_id):
    data = request.json
    if not all(k in data for k in ['username', 'text']):
        return jsonify({'error': 'Missing required fields'}), 400
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404
    user = User.query.filter(db.func.lower(User.username) == db.func.lower(data['username'])).first()
    if not user or user.id != comment.user_id:
        return jsonify({'error': 'Permission denied'}), 403
    comment.text = data['text']
    db.session.commit()
    return jsonify({'status': 'success'}), 200

@app.route('/api/comments/<int:comment_id>', methods=['DELETE'])
def delete_comment(comment_id):
    data = request.json
    if not data or 'username' not in data:
        return jsonify({'error': 'Missing username'}), 400
    comment = Comment.query.get(comment_id)
    if not comment:
        return jsonify({'error': 'Comment not found'}), 404
    user = User.query.filter(db.func.lower(User.username) == db.func.lower(data['username'])).first()
    if not user or user.id != comment.user_id:
        return jsonify({'error': 'Permission denied'}), 403
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'status': 'success'}), 200

if __name__ == '__main__':
    import threading
    from mllp_server import HL7MLLPServer
    import signal
    import sys
    import os
    
    # Create database tables
    with app.app_context():
        db.create_all()
    
    # Start MLLP server in a separate thread
    mllp_server = HL7MLLPServer()
    mllp_thread = threading.Thread(target=mllp_server.start, daemon=True)
    
    try:
        mllp_thread.start()
    except Exception as e:
        print(f"Error starting MLLP server: {e}")
        print("Continuing with HTTP server only...")
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        print("\nShutting down servers...")
        mllp_server.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Get environment configuration
    debug_mode = os.getenv('FLASK_ENV', 'production') == 'development'
    host = os.getenv('FLASK_HOST', '0.0.0.0')
    port = int(os.getenv('FLASK_PORT', 5000))
    
    # Start Flask server
    if debug_mode:
        print("Running in development mode")
        app.run(host=host, port=port, debug=True)
    else:
        print("Running in production mode")
        # Use a production WSGI server
        from waitress import serve
        serve(app, host=host, port=port) 