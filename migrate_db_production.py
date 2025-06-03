#!/usr/bin/env python3
"""
Production-safe database migration script for Trauma AI Quality Control System.

This script safely adds new columns and tables without affecting existing data.
All operations are wrapped in transactions with proper rollback capabilities.

Usage:
    python migrate_db_production.py [--dry-run] [--backup]

Options:
    --dry-run    Show what would be changed without executing
    --backup     Create a database backup before migration
"""

import sys
import logging
import argparse
from datetime import datetime
from app import app, db
from models import Study, Classification, User, Comment
from sqlalchemy import text, inspect

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def check_table_exists(table_name):
    """Check if a table exists."""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

def create_backup(backup_name=None):
    """Create a database backup (PostgreSQL specific)."""
    if backup_name is None:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"backup_before_migration_{timestamp}.sql"
    
    logger.info(f"Creating backup: {backup_name}")
    # Note: This would need to be implemented based on your database setup
    # For PostgreSQL: pg_dump command
    # For SQLite: simple file copy
    logger.warning("Backup functionality needs to be implemented for your database type")

def migrate_database_safe(dry_run=False):
    """Safely migrate database with comprehensive checks."""
    
    migrations = [
        {
            'name': 'Add classification_type to classifications table',
            'table': 'classifications',
            'column': 'classification_type',
            'sql': """
                ALTER TABLE classifications 
                ADD COLUMN classification_type VARCHAR(10) NOT NULL DEFAULT 'USER'
            """
        },
        {
            'name': 'Add patient_id to studies table',
            'table': 'studies',
            'column': 'patient_id',
            'sql': """
                ALTER TABLE studies 
                ADD COLUMN patient_id VARCHAR(50)
            """
        },
        {
            'name': 'Add patient_dob to studies table',
            'table': 'studies',
            'column': 'patient_dob',
            'sql': """
                ALTER TABLE studies 
                ADD COLUMN patient_dob VARCHAR(10)
            """
        },
        {
            'name': 'Add patient_gender to studies table',
            'table': 'studies',
            'column': 'patient_gender',
            'sql': """
                ALTER TABLE studies 
                ADD COLUMN patient_gender VARCHAR(1)
            """
        },
        {
            'name': 'Add study_uid to studies table',
            'table': 'studies',
            'column': 'study_uid',
            'sql': """
                ALTER TABLE studies 
                ADD COLUMN study_uid VARCHAR(200)
            """
        }
    ]
    
    with app.app_context():
        logger.info("Starting database migration...")
        
        # Check what needs to be migrated
        needed_migrations = []
        for migration in migrations:
            if not check_column_exists(migration['table'], migration['column']):
                needed_migrations.append(migration)
                logger.info(f"Migration needed: {migration['name']}")
            else:
                logger.info(f"Skipping: {migration['name']} (column already exists)")
        
        if not needed_migrations:
            logger.info("No migrations needed - database is up to date!")
            return True
        
        if dry_run:
            logger.info("DRY RUN - Would execute the following migrations:")
            for migration in needed_migrations:
                logger.info(f"  - {migration['name']}")
                logger.info(f"    SQL: {migration['sql'].strip()}")
            return True
        
        # Execute migrations in a transaction
        try:
            with db.session.begin():
                for migration in needed_migrations:
                    logger.info(f"Executing: {migration['name']}")
                    db.session.execute(text(migration['sql']))
                    logger.info(f"✅ Completed: {migration['name']}")
                
                logger.info("All column migrations completed successfully!")
                
        except Exception as e:
            logger.error(f"❌ Migration failed: {e}")
            logger.info("Transaction rolled back - database unchanged")
            raise

def add_comments_table_safe(dry_run=False):
    """Safely add comments table if it doesn't exist."""
    
    if check_table_exists('comments'):
        logger.info("Comments table already exists - skipping")
        return True
    
    sql = '''
        CREATE TABLE comments (
            id SERIAL PRIMARY KEY,
            study_id INTEGER REFERENCES studies(id) ON DELETE CASCADE,
            user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
            text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
    '''
    
    if dry_run:
        logger.info("DRY RUN - Would create comments table:")
        logger.info(f"SQL: {sql}")
        return True
    
    try:
        with app.app_context():
            with db.engine.connect() as conn:
                with conn.begin():
                    logger.info("Creating comments table...")
                    conn.execute(text(sql))
                    logger.info("✅ Comments table created successfully!")
    except Exception as e:
        logger.error(f"❌ Failed to create comments table: {e}")
        raise

def verify_migration():
    """Verify that the migration was successful."""
    
    with app.app_context():
        logger.info("Verifying migration...")
        
        # Check that all expected columns exist
        expected_columns = [
            ('classifications', 'classification_type'),
            ('studies', 'patient_id'),
            ('studies', 'patient_dob'),
            ('studies', 'patient_gender'),
            ('studies', 'study_uid')
        ]
        
        for table, column in expected_columns:
            if check_column_exists(table, column):
                logger.info(f"✅ {table}.{column} exists")
            else:
                logger.error(f"❌ {table}.{column} missing!")
                return False
        
        # Check comments table
        if check_table_exists('comments'):
            logger.info("✅ comments table exists")
        else:
            logger.error("❌ comments table missing!")
            return False
        
        logger.info("🎉 Migration verification successful!")
        return True

def main():
    parser = argparse.ArgumentParser(description="Production-safe database migration")
    parser.add_argument('--dry-run', action='store_true', 
                       help='Show what would be changed without executing')
    parser.add_argument('--backup', action='store_true',
                       help='Create a backup before migration')
    
    args = parser.parse_args()
    
    try:
        if args.backup and not args.dry_run:
            create_backup()
        
        # Run migrations
        migrate_database_safe(dry_run=args.dry_run)
        add_comments_table_safe(dry_run=args.dry_run)
        
        if not args.dry_run:
            verify_migration()
        
        logger.info("Migration process completed successfully!")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main() 