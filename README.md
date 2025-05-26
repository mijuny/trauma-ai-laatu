# Trauma AI laadunvalvonta

A web application for monitoring and analyzing the performance of trauma AI systems in a hospital setting. This application helps track and evaluate the accuracy of AI-based trauma detection systems by comparing AI predictions with radiologist classifications.

## Features

- HL7 message integration for receiving AI analysis results
- Web interface for viewing and classifying studies
- Statistical analysis of AI performance
- CSV export functionality
- Dark/light mode support

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create a `.env` file with the following content:
```
DATABASE_URL=postgresql://localhost/radiology_ai
FLASK_SECRET_KEY=your-secret-key-here
FLASK_ENV=development
```

4. Initialize the database:
```bash
python init_db.py
```

5. Run the application:
```bash
python app.py
```

## HL7 Message Integration

The application accepts HL7 messages at the `/api/hl7` endpoint. The message format should follow the Gleamer AI system's structure:

```
MSH|^~\\&|GLEAMER|HOSPITAL|PACS|HOSPITAL|20240315123456||ORU^R01|MSGID123|P|2.5
PID|||12345|||19800101|M
OBR|1|12345|12345|CT CHEST||20240315123456|||||||||||||||||||F
OBX|1|ST|AI_RESULT||POSITIVE||||||F
```

### Result Interpretation

- `POSITIVE` in OBX-5: Initial classification as TP (True Positive)
- `NEGATIVE` in OBX-5: Initial classification as TN (True Negative)

## Performance Metrics

The application calculates the following metrics:

- Sensitivity (True Positive Rate)
- Specificity (True Negative Rate)
- Accuracy
- Positive Predictive Value (PPV)
- Negative Predictive Value (NPV)
- F1 Score

## Database Structure

The application uses PostgreSQL with the following tables:

### Studies Table
- `id`: Primary key
- `accession_number`: Unique identifier for the study
- `study_description`: Description of the study
- `raw_hl7`: Original HL7 message
- `parsed_data`: Parsed HL7 data including original AI result
- `ai_classification`: Initial AI classification (TP/TN)
- `created_at`: Timestamp

### Classifications Table
- `id`: Primary key
- `study_id`: Foreign key to studies table
- `username`: Name of the radiologist
- `classification`: User classification (TP/TN/FP/FN)
- `created_at`: Timestamp

## Debugging HL7 Messages

To view stored HL7 messages in the database:

```sql
-- View all studies with their HL7 messages
SELECT accession_number, raw_hl7, ai_classification, created_at 
FROM studies 
ORDER BY created_at DESC;

-- View studies with specific classifications
SELECT s.accession_number, s.ai_classification, c.classification as user_classification
FROM studies s
LEFT JOIN classifications c ON s.id = c.study_id
WHERE s.ai_classification = 'TP' OR c.classification = 'TP';
```

## Contributing

Please read CONTRIBUTING.md for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details. 