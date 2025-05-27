import os
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template, send_file, session, redirect
from flask_sqlalchemy import SQLAlchemy
from models import db, Study, Classification, User
import hl7
import csv
from io import StringIO
from dateutil import parser
from dotenv import load_dotenv
from translations import TRANSLATIONS

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('DATABASE_URL', 'postgresql://localhost/radiology_ai')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'dev')

db.init_app(app)

def get_translation(key, lang='fi'):
    """Get translation for a given key in the specified language."""
    return TRANSLATIONS.get(lang, TRANSLATIONS['fi']).get(key, key)

@app.context_processor
def inject_translations():
    """Inject translations into all templates."""
    lang = session.get('lang', 'fi')
    return dict(t=get_translation, lang=lang, min=min, max=max)

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
        print("\nAvailable segments:")
        for segment in h.segments():
            print(f"Segment: {segment}")
        
        # Extract fields from the message
        try:
            # Get MSH segment
            msh_segment = h.segment('MSH')
            print("\nMSH segment:", msh_segment)
            
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
            
            # Extract fields with proper error handling
            accession_number = str(obr_segment[2][0]) if len(obr_segment) > 2 else None
            study_description = str(obr_segment[4][0]) if len(obr_segment) > 4 else None
            result = str(obx_segment[5][0]).upper() if len(obx_segment) > 5 else None
            
            # Extract additional fields
            patient_id = str(pid_segment[2][0]) if len(pid_segment) > 2 else None
            patient_dob = str(pid_segment[6][0]) if len(pid_segment) > 6 else None
            patient_gender = str(pid_segment[7][0]) if len(pid_segment) > 7 else None
            study_uid = str(zds_segment[0][0]) if zds_segment and len(zds_segment) > 0 else None
            
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
            
            return {
                'accession_number': accession_number,
                'study_description': study_description,
                'ai_classification': result,
                'raw_result': result,
                'patient_id': patient_id,
                'patient_dob': patient_dob,
                'patient_gender': patient_gender,
                'study_uid': study_uid
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
                    accession_number = str(obr_segment[2][0])
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
                patient_dob = str(pid_segment[6][0]) if len(pid_segment) > 6 else None
                patient_gender = str(pid_segment[7][0]) if len(pid_segment) > 7 else None
                
                # Get ZDS segment if available
                zds_segment = h.segment('ZDS')
                study_uid = str(zds_segment[0][0]) if zds_segment and len(zds_segment) > 0 else None
                
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
                        'study_uid': study_uid
                    },
                    ai_classification=result,
                    patient_id=patient_id,
                    patient_dob=patient_dob,
                    patient_gender=patient_gender,
                    study_uid=study_uid
                )
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
    if not all(k in data for k in ['study_id', 'username', 'classification']):
        return jsonify({'error': 'Missing required fields'}), 400
    
    # Validate classification value
    valid_classifications = ['POSITIVE', 'NEGATIVE']
    if data['classification'] not in valid_classifications:
        return jsonify({'error': 'Invalid classification value'}), 400
    
    # Check if study exists - using Session.get() instead of Query.get()
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
    
    # Determine the final classification based on AI and user input
    ai_classification = study.ai_classification
    user_classification = data['classification']
    
    # Convert AI classification to POSITIVE/NEGATIVE if it's TP/TN
    if ai_classification in ['TP', 'FP']:
        ai_classification = 'POSITIVE'
    elif ai_classification in ['TN', 'FN']:
        ai_classification = 'NEGATIVE'
    
    # Determine final classification
    if ai_classification == 'POSITIVE' and user_classification == 'POSITIVE':
        final_classification = 'TP'
    elif ai_classification == 'NEGATIVE' and user_classification == 'NEGATIVE':
        final_classification = 'TN'
    elif (ai_classification == 'POSITIVE' or ai_classification == 'DOUBT') and user_classification == 'NEGATIVE':
        final_classification = 'FP'
    elif ai_classification == 'NEGATIVE' and user_classification == 'POSITIVE':
        final_classification = 'FN'
    else:
        return jsonify({'error': f'Invalid classification combination: AI={ai_classification}, User={user_classification}'}), 400
    
    # Check for existing classification by the same user for this study
    existing_classification = Classification.query.filter(
        Classification.study_id == data['study_id'],
        Classification.user_id == user.id
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
            classification=final_classification
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
    
    # Apply filters
    if time_filter != 'all':
        if time_filter == 'today':
            query = query.filter(Study.created_at >= datetime.now().date())
        elif time_filter == 'week':
            query = query.filter(Study.created_at >= datetime.now() - timedelta(days=7))
        elif time_filter == 'month':
            query = query.filter(Study.created_at >= datetime.now() - timedelta(days=30))
    
    if study_type:
        query = query.filter(Study.accession_number.ilike(f'%{study_type}%'))
    
    # Get filtered studies for display with pagination
    studies = query.order_by(Study.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    
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
        filtered_studies = []
        for study in studies.items:
            user_classification = user_classification_map.get(study.id)
            
            # If there's a user classification, use it
            if user_classification:
                if user_classification == result_type:
                    filtered_studies.append(study)
            # If no user classification, check AI classification
            else:
                # For TP filter, include studies with POSITIVE or DOUBT AI classification
                if result_type == 'TP' and study.ai_classification in ['POSITIVE', 'DOUBT']:
                    filtered_studies.append(study)
                # For TN filter, include studies with NEGATIVE AI classification
                elif result_type == 'TN' and study.ai_classification == 'NEGATIVE':
                    filtered_studies.append(study)
                # For DOUBT filter, include studies with DOUBT AI classification
                elif result_type == 'DOUBT' and study.ai_classification == 'DOUBT':
                    filtered_studies.append(study)
                # For FP and FN, only include if there's a user classification
                elif result_type in ['FP', 'FN']:
                    continue
        
        # Create a custom pagination object for filtered results
        total = len(filtered_studies)
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        filtered_items = filtered_studies[start_idx:end_idx]
        
        # Create a custom pagination object
        class CustomPagination:
            def __init__(self, items, page, per_page, total):
                self.items = items
                self.page = page
                self.per_page = per_page
                self.total = total
                self.pages = (total + per_page - 1) // per_page
                self.has_next = page < self.pages
                self.has_prev = page > 1
                self.prev_num = page - 1 if page > 1 else None
                self.next_num = page + 1 if page < self.pages else None
        
        studies = CustomPagination(filtered_items, page, per_page, total)
    
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
        user_classification = all_classification_map.get(study.id)
        
        if user_classification:
            # User has provided a classification
            if user_classification == 'TP':
                tp_count += 1
            elif user_classification == 'TN':
                tn_count += 1
            elif user_classification == 'FP':
                fp_count += 1
            elif user_classification == 'FN':
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
                         lang=lang)

@app.route('/export')
def export_csv():
    """Export studies to CSV."""
    studies = Study.query.all()
    
    output = StringIO()
    cw = csv.writer(output)
    
    # Write header
    cw.writerow([
        'Study Date',
        'Accession Number',
        'Study Description',
        'AI Classification',
        'User Classification',
        'Original Result',
        'Patient ID',
        'Patient DOB',
        'Patient Gender',
        'Study UID'
    ])
    
    # Write data
    for study in studies:
        # Get the latest classification for this study
        latest_classification = Classification.query.filter_by(study_id=study.id).order_by(Classification.created_at.desc()).first()
        user_classification = latest_classification.classification if latest_classification else ''
        
        cw.writerow([
            study.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            study.accession_number,
            study.study_description,
            study.ai_classification,
            user_classification,
            study.parsed_data.get('raw_result', ''),
            study.patient_id or '',
            study.patient_dob or '',
            study.patient_gender or '',
            study.study_uid or ''
        ])
    
    output.seek(0)
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'radiology_studies_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

@app.route('/reset_filters')
def reset_filters():
    """Reset all filters and redirect to the main page."""
    username = request.args.get('username', '')
    if username:
        return redirect(f'/?username={username}')
    return redirect('/')

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