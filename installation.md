# Trauma AI Quality Control System - Installation Guide

## System Requirements
- Ubuntu 22.04 LTS or newer
- Python 3.10 or newer
- PostgreSQL 14 or newer
- At least 2GB RAM
- At least 20GB disk space

## 1. System Setup

```bash
# Update system packages
sudo apt update
sudo apt upgrade -y

# Install required system packages
sudo apt install -y python3.10 python3.10-venv python3-pip postgresql postgresql-contrib git

# Install development tools (optional, for debugging)
sudo apt install -y build-essential python3-dev
```

## 2. PostgreSQL Setup

```bash
# Start PostgreSQL service
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Create database and user
sudo -u postgres psql -c "CREATE DATABASE radiology_ai;"
sudo -u postgres psql -c "CREATE USER radiology_user WITH PASSWORD 'your_secure_password';"
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE radiology_ai TO radiology_user;"
```

## 3. Application Setup

```bash
# Create application directory
sudo mkdir -p /opt/trauma-ai
sudo chown $USER:$USER /opt/trauma-ai

# Clone repository
git clone https://github.com/your-repo/trauma-ai-laatu.git /opt/trauma-ai
cd /opt/trauma-ai

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install --upgrade pip
pip install -r requirements.txt
```

## 4. Environment Configuration

Create a `.env` file in the application directory:

```bash
# Create .env file
cat > .env << EOL
DATABASE_URL=postgresql://radiology_user:your_secure_password@localhost/radiology_ai
FLASK_SECRET_KEY=your_secure_secret_key
FLASK_ENV=production
FLASK_HOST=0.0.0.0
FLASK_PORT=5000
MLLP_PORT=8000
EOL
```

## 5. Database Initialization

```bash
# Initialize database
python init_db.py
python migrate_db.py
```

## 6. Systemd Service Setup

Create a systemd service file for the application:

```bash
sudo nano /etc/systemd/system/trauma-ai.service
```

Add the following content:

```ini
[Unit]
Description=Trauma AI Quality Control System
After=network.target postgresql.service

[Service]
User=your_username
Group=your_group
WorkingDirectory=/opt/trauma-ai
Environment="PATH=/opt/trauma-ai/venv/bin"
ExecStart=/opt/trauma-ai/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start the service:

```bash
sudo systemctl daemon-reload
sudo systemctl enable trauma-ai
sudo systemctl start trauma-ai
```

## 7. Testing Setup

For testing purposes, you can use the included test script:

```bash
# Generate test cases
python test_hl7.py -n 10  # Generates 10 test cases
```

## 8. Monitoring and Logging

```bash
# View application logs
sudo journalctl -u trauma-ai -f

# Check service status
sudo systemctl status trauma-ai
```

## 9. Security Considerations

1. Configure firewall:
```bash
sudo ufw allow 5000/tcp  # HTTP API
sudo ufw allow 8000/tcp  # MLLP server
```

2. Set up SSL/TLS (recommended for production):
```bash
# Install certbot
sudo apt install -y certbot python3-certbot-nginx

# Get SSL certificate
sudo certbot certonly --standalone -d your-domain.com
```

## 10. Backup Setup

Create a backup script:

```bash
#!/bin/bash
# /opt/trauma-ai/backup.sh

BACKUP_DIR="/opt/trauma-ai/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR

# Backup database
pg_dump -U radiology_user radiology_ai > $BACKUP_DIR/db_backup_$TIMESTAMP.sql

# Backup application files
tar -czf $BACKUP_DIR/app_backup_$TIMESTAMP.tar.gz /opt/trauma-ai

# Keep only last 7 days of backups
find $BACKUP_DIR -type f -mtime +7 -delete
```

Make it executable and set up a cron job:

```bash
chmod +x /opt/trauma-ai/backup.sh
crontab -e

# Add this line to run backup daily at 2 AM
0 2 * * * /opt/trauma-ai/backup.sh
```

## 11. Package Versions

The application uses the following key package versions:
- Flask==3.0.2
- psycopg2-binary==2.9.9
- python-dotenv==1.0.1
- hl7>=0.4.5
- Flask-SQLAlchemy==3.1.1
- python-dateutil==2.8.2
- python-hl7-mllp==0.1.0
- waitress==3.0.0

## 12. Testing the Installation

1. Test HTTP API:
```bash
curl -X POST http://localhost:5000/api/hl7 \
  -H "Content-Type: text/plain" \
  -d "$(python test_hl7.py -n 1)"
```

2. Test MLLP server:
```bash
# Install MLLP test client
pip install hl7-mllp-client

# Send test message
python -c "
from hl7_mllp_client import MLLPClient
client = MLLPClient('localhost', 8000)
message = 'MSH|^~\\&|GLEAMER||CSILXD|LUXMED|20240315123456||ORU^R01|MSGID123|P|2.5'
response = client.send_message(message)
print(response)
"
```

## 13. Troubleshooting

Common issues and solutions:

1. Database connection issues:
```bash
# Check PostgreSQL logs
sudo tail -f /var/log/postgresql/postgresql-14-main.log

# Test database connection
psql -U radiology_user -d radiology_ai -h localhost
```

2. Port conflicts:
```bash
# Check if ports are in use
sudo lsof -i :5000
sudo lsof -i :8000
```

3. Permission issues:
```bash
# Fix permissions
sudo chown -R your_username:your_group /opt/trauma-ai
sudo chmod -R 755 /opt/trauma-ai
```

## 14. API Endpoints

The system provides the following API endpoints:

1. HL7 Message Reception:
   - HTTP: `POST http://localhost:5000/api/hl7`
   - MLLP: `localhost:8000`

2. Study Classification:
   - `POST http://localhost:5000/api/classify`
   - Required fields: study_id, username, classification

3. User Management:
   - `POST http://localhost:5000/api/username`
   - Required fields: username

4. Data Export:
   - `GET http://localhost:5000/export`
   - Returns CSV file with all studies and classifications

## 15. Maintenance

Regular maintenance tasks:

1. Database cleanup:
```bash
# Connect to database
psql -U radiology_user -d radiology_ai

# Remove old studies (older than 1 year)
DELETE FROM studies WHERE created_at < NOW() - INTERVAL '1 year';
```

2. Log rotation:
```bash
# Configure log rotation
sudo nano /etc/logrotate.d/trauma-ai

# Add configuration
/var/log/trauma-ai/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 your_username your_group
}
```

3. System updates:
```bash
# Update system packages
sudo apt update
sudo apt upgrade

# Update Python packages
source /opt/trauma-ai/venv/bin/activate
pip install --upgrade -r requirements.txt
```

## 16. Support

For support and issues:
1. Check the application logs: `sudo journalctl -u trauma-ai -f`
2. Review PostgreSQL logs: `/var/log/postgresql/postgresql-14-main.log`
3. Check system resources: `htop`
4. Monitor network connections: `netstat -tulpn | grep -E '5000|8000'` 