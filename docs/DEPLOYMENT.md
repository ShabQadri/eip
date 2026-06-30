# Entertainment Intelligence Platform (EIP) – Deployment Guide

This guide provides the complete, copy-paste ready instructions for deploying EIP to an Oracle Linux server (Free Tier compatible).

---

## 1. Local Cleanup Checklist
Before pushing code, clean up any local temporary development files to prevent transferring untracked state or large binaries:
```bash
# Remove Python bytecode cache
find . -type d -name "__pycache__" -exec rm -r {} +

# Remove pytest cache files
rm -rf .pytest_cache

# Remove local database and log files if present
rm -rf data/sqlite/entertainment.db
rm -rf data/logs/*
rm -rf data/images/*
```

## 2. Git Push Checklist
Ensure all tests are passing and changes are committed cleanly before deploying:
```bash
# Run full test suite locally
.venv/Scripts/pytest -q

# Check status for untracked files
git status

# Commit and push changes
git add .
git commit -m "chore: prepare release for deployment"
git push origin main
```

## 3. Oracle Server Setup
Connect to your remote Oracle Linux instance and check current workspace directory structure:
```bash
# SSH into the server (replace ip and keypath)
ssh -i /path/to/key.key opc@your-oracle-server-ip

# Install git if missing
sudo dnf install -y git

# Create application directory
sudo mkdir -p /var/www/eip
sudo chown -R opc:opc /var/www/eip
cd /var/www/eip

# Clone repository (if first-time setup)
git clone https://github.com/your-username/entertainment-intelligence-platform.git .
# OR pull latest changes (if upgrading)
git pull origin main
```

## 4. Python Virtual Environment Setup
Create a dedicated python environment for the application:
```bash
# Check python version (minimum 3.12 required)
python3 --version

# Create virtual environment
python3 -m venv .venv

# Activate virtual environment
source .venv/bin/activate
```

## 5. Requirements Installation
Install required packages using the virtual environment's pip:
```bash
# Ensure pip is up to date
pip install --upgrade pip

# Install project dependencies
pip install -r requirements.txt
```

## 6. Environment Variable Setup
Create a `.env` configuration file in the project root:
```bash
# Create .env from template
cp .env.example .env

# Open and edit env file
nano .env
```
Ensure the following variables are correctly configured:
```ini
APP_ENV=production
LOG_LEVEL=INFO
TELEGRAM_BOT_TOKEN=123456789:ABCdefGh...
TELEGRAM_CHANNEL_ID=-1001234567890
GEMINI_API_KEY=AIzaSy...
DATABASE_URL=sqlite:////var/www/eip/data/sqlite/entertainment.db
```

## 7. Database Initialization
Create database directories, tables, and indexes, and seed the default configuration settings:
```bash
# Run database initializer
python scripts/init_db.py
```

## 8. Startup Self-Test
Verify that the database connection, feed files, credentials, and tables are fully valid. The self-test will fail fast on any error:
```bash
# Run application startup self-test
python src/main.py
```
Expected output:
```text
2026-06-30 14:15:30 | INFO | main | Running startup self-test...
2026-06-30 14:15:30 | INFO | main | Self-test results: {"database": "ok", "metrics_table": "ok", "publication_table": "ok", "scheduler": "ok", "feed_configs": "ok", "telegram": "ok"}
2026-06-30 14:15:30 | INFO | main | Self-test successful.
2026-06-30 14:15:30 | INFO | main | Application initialized
Entertainment Intelligence Platform initialized.
```

## 9. Systemd Service Setup
Configure EIP to run continuously in the background and auto-restart on system boot.
Create the service unit file:
```bash
sudo nano /etc/systemd/system/eip.service
```
Paste the following configuration:
```ini
[Unit]
Description=Entertainment Intelligence Platform Service
After=network.target

[Service]
Type=simple
User=opc
WorkingDirectory=/var/www/eip
ExecStart=/var/www/eip/.venv/bin/python src/main.py
Restart=always
RestartSec=10
Environment=PYTHONPATH=/var/www/eip

[Install]
WantedBy=multi-user.target
```
Enable and start the service:
```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable service to run on boot
sudo systemctl enable eip.service

# Start EIP service
sudo systemctl start eip.service
```

## 10. Service Verification
Check that the systemd service is active and running cleanly:
```bash
sudo systemctl status eip.service
```

## 11. Log Monitoring
Monitor real-time application logs using journalctl:
```bash
# View live service logs
journalctl -u eip.service -f -n 100
```

## 12. Telegram Verification
Check your configured Telegram channel to ensure that startup notification or heartbeat tests succeed without errors.

## 13. Health Checks
Verify all subsystems are functional using the health CLI one-liner:
```bash
python -c "import json; from src.database.database import SessionLocal; from src.services.health_service import HealthService; db=SessionLocal(); print(json.dumps(HealthService().get_system_health(db), indent=2)); db.close()"
```
Expected Output:
```json
{
  "status": "healthy",
  "details": {
    "database": {
      "status": "healthy",
      "details": {
        "connection": "ok",
        "tables": {
          "system_metrics": "ok",
          "published_posts": "ok"
        }
      }
    },
    "scheduler": {
      "status": "healthy",
      "details": {
        "running": true,
        "job_count": 5
      }
    },
    "feeds": {
      "status": "healthy",
      "details": {
        "total_feeds": 14,
        "enabled_feeds": 14,
        "disabled_feeds": 0,
        "dead_feeds_list": []
      }
    },
    "telegram": {
      "status": "healthy",
      "details": {
        "token_format": "valid",
        "channel_id_present": "valid"
      }
    }
  }
}
```

## 14. Metrics Verification
Ensure metrics are recorded by checking the daily metrics summary:
```bash
python -c "import json; from src.database.database import SessionLocal; from src.services.metrics_service import MetricsService; db=SessionLocal(); print(json.dumps(MetricsService().daily_metrics_summary(db), indent=2)); db.close()"
```

## 15. Upgrade Procedure
When upgrading EIP to a new version on the server, execute:
```bash
# Navigate to repository directory
cd /var/www/eip

# Pull latest commits
git pull origin main

# Update dependencies if required
.venv/bin/pip install -r requirements.txt

# Run any migrations or database updates
.venv/bin/python scripts/init_db.py

# Restart the application service
sudo systemctl restart eip.service

# Verify upgraded state
sudo systemctl status eip.service
```
