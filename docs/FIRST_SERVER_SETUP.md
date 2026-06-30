# Entertainment Intelligence Platform (EIP) – First Server Setup Guide

This guide details the complete workflow to bootstrap, install, and configure EIP on a brand-new Oracle Linux 9 server instance.

---

## 1. System Package Updates
Update the package registry and install updates:
```bash
# Update server repositories
sudo dnf update -y
```

## 2. Install Development Tools
Install git, python3.12, python3.12-pip, python3.12-devel, and sqlite3 database:
```bash
# Install git and sqlite
sudo dnf install -y git sqlite

# Install Python 3.12 stack
sudo dnf install -y python3.12 python3.12-pip python3.12-devel
```

## 3. Configure Workspace Directories
Create the deployment folder and assign the default Oracle user ownership:
```bash
# Create directory structure
sudo mkdir -p /var/www/eip
sudo chown -R opc:opc /var/www/eip

# Navigate to deploy path
cd /var/www/eip
```

## 4. Clone Repository
Clone the codebase directly from GitHub:
```bash
# Clone project repo
git clone https://github.com/your-username/entertainment-intelligence-platform.git .
```

## 5. Virtual Environment Initialization
Set up a clean virtual environment using the python3.12 executable:
```bash
# Create environment
python3.12 -m venv .venv

# Activate environment
source .venv/bin/activate
```

## 6. Install Project Dependencies
Upgrade pip and install the required modules:
```bash
# Upgrade installer tools
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt
```

## 7. Configure Environment Settings
Create and configure your `.env` settings file:
```bash
# Copy settings template
cp .env.example .env

# Edit .env parameters
nano .env
```
Ensure you update:
* `TELEGRAM_BOT_TOKEN`
* `TELEGRAM_CHANNEL_ID`
* `GEMINI_API_KEY`
* `DATABASE_URL` (e.g. `sqlite:////var/www/eip/data/sqlite/entertainment.db`)

## 8. Initialize SQLite Database
Initialize data directories and create the database file:
```bash
# Run seeder and database initialization
python scripts/init_db.py
```

## 9. Create Systemd Service File
Configure the systemd service to run the EIP background application:
```bash
# Open systemd service nano editor
sudo nano /etc/systemd/system/eip.service
```
Paste the following configurations:
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

## 10. Start and Enable Service
Reload systemd, enable the service to start automatically on server boot, and start EIP:
```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable service for boot autostart
sudo systemctl enable eip.service

# Start EIP service
sudo systemctl start eip.service
```

## 11. Verify Setup and Operation
Confirm EIP is running cleanly without exceptions:
```bash
# Check service status
sudo systemctl status eip.service

# Verify startup self-test output in logs
journalctl -u eip.service -n 50 --no-pager
```
*Tip: If status is `active (running)`, EIP is successfully bootstrapped and operating on your server!*
