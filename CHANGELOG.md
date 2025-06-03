# Changelog

All notable changes to the Trauma AI Quality Control System will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2024-06-03
### Added
- Comprehensive dark mode implementation with persistent user preference
  - Dark theme for all UI components including headers, content sections, forms, and tables
  - Professional dark color scheme with proper contrast ratios
  - Theme preference stored in browser localStorage and persists across page reloads and user interactions
- Enhanced translation system with improved context processor functionality
  - Fixed language switching between Finnish and English
  - Proper session-based language persistence across all user interactions
  - Improved translation function architecture for better maintainability
- Database migration tools for safe schema updates
  - `migrate_db.py` - Basic migration script for development environments
  - `migrate_db_production.py` - Production-safe migration with comprehensive safety features:
    - Dry-run mode to preview changes before execution
    - Backup creation capabilities
    - Transactional operations with automatic rollback on errors
    - Column and table existence checks to prevent conflicts
    - Detailed logging and verification steps
    - Support for adding new columns (classification_type, patient_id, patient_dob, patient_gender, study_uid)
    - Comments table creation for study annotations

### Fixed
- Language dropdown functionality - selecting English now properly changes the interface language
- Dark mode persistence - theme selection now maintained across page refreshes, form submissions, and navigation
- Header button styling in dark mode (language selector and theme toggle)
- Content section backgrounds and borders for consistent dark theme appearance
- CSS specificity issues causing inconsistent theme application

### Changed
- Improved theme toggle implementation with localStorage integration
- Enhanced CSS architecture for better dark mode support
- More robust translation function that automatically uses session language

## [1.1.1] - 2024-05-30
### Changed
- Removed automatic page refresh; added a "Päivitä" (Refresh) button next to "Tyhjennä suodattimet".
- Fixed: AI result "DOUBT" (Epävarma) is now handled as POSITIVE in all classification logic and statistics, but still shown as "DOUBT" in the UI.

## [1.1.0] - 2024-05-28
### Added
- Follow-up classification (Jatkotutkimus) support: cases can now be classified as POSITIVE or NEGATIVE by follow-up, with independent logic and override rules.
- Comment history for each case: users can add, edit, and delete comments; most recent comment is shown in the case list; all comments viewable in a modal.
- Any user can now create, edit, or remove any classification (user or follow-up).
- UI improvements: single dropdown for all classification actions, improved error messages, and more compact comment input with "Näytä kommentit" button.
- Finnish error messages for classification removal when none exists.

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
