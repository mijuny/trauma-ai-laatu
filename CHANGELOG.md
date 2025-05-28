# Changelog

All notable changes to the Trauma AI Quality Control System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.2] - 2024-03-28

### Added
- New filter option "My Classified Cases" to show only cases classified by the selected user
- Added translations for the new filter in both Finnish and English

## [1.0.1] - 2024-03-28

### Changed
- Optimized PACS viewer window behavior to be minimal and non-intrusive
- Improved user experience when opening PACS viewer from AC numbers

## [1.0.0] - 2024-03-15

### Added
- Initial production release of the Trauma AI Quality Control System
- Core Features:
  - HL7 message integration for receiving AI analysis results
  - Web interface for viewing and classifying studies
  - Statistical analysis of AI performance
  - CSV export functionality
  - Dark/light mode support
  - Multi-language support (Finnish/English)

### Technical Details
- Database:
  - PostgreSQL integration with SQLAlchemy ORM
  - Studies table for storing examination data
  - Classifications table for radiologist reviews
  - Automatic timestamp handling in Finnish timezone

- HL7 Integration:
  - MLLP server for receiving HL7 messages
  - Support for Gleamer AI system message format
  - Automatic parsing of MSH, PID, OBR, and OBX segments
  - Error handling and validation for HL7 messages

- Web Interface:
  - Flask-based web application
  - Responsive design
  - Real-time statistics
  - Filtering capabilities:
    - By time period (today/week/month)
    - By study type
    - By result type
    - By username

- Performance Metrics:
  - Sensitivity (True Positive Rate)
  - Specificity (True Negative Rate)
  - Accuracy
  - Positive Predictive Value (PPV)
  - Negative Predictive Value (NPV)
  - F1 Score

### Dependencies
- Flask 3.0.2
- psycopg2-binary 2.9.9
- python-dotenv 1.0.1
- hl7 0.4.5+
- Flask-SQLAlchemy 3.1.1
- python-dateutil 2.8.2
- waitress 3.0.0
- hl7apy
- pytz 2024.1

### Security
- Environment variable configuration
- Secure session handling
- Input validation for HL7 messages
- SQL injection prevention through SQLAlchemy

### Deployment
- Production-ready with Waitress WSGI server
- Development mode support
- Database migration support
- Database reset functionality for testing 