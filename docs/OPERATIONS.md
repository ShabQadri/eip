# Entertainment Intelligence Platform (EIP) – Operations Manual

This manual contains copy-paste ready administrative commands for EIP daily monitoring, weekly maintenance, and monthly updates.

---

## 1. Daily Operations

### Check Service Status
Verify systemd daemon status of EIP:
```bash
sudo systemctl status eip.service
```

### Check Logs
Read recent application logs and monitor live execution:
```bash
# View last 50 log lines
journalctl -u eip.service -n 50

# Follow live output
journalctl -u eip.service -f
```

### Health Report
Query system health overview (returns JSON):
```bash
python -c "import json; from src.database.database import SessionLocal; from src.services.health_service import HealthService; db=SessionLocal(); print(json.dumps(HealthService().get_system_health(db), indent=2)); db.close()"
```

### Admin Report
Query the daily administrative summary containing metrics and status details:
```bash
python -c "import json; from src.database.database import SessionLocal; from src.services.health_service import HealthService; db=SessionLocal(); print(json.dumps(HealthService().generate_daily_admin_report(db), indent=2)); db.close()"
```

### Database Size
Check SQLite database file size directly from disk:
```bash
ls -lh data/sqlite/entertainment.db
```

### Disk Usage
Check total server disk space left to prevent out-of-space crashes:
```bash
df -h
```

### Restart Service
If service is unstable or unresponsive, trigger a reload restart:
```bash
sudo systemctl restart eip.service
```

---

## 2. Weekly Operations

### Database Backup
Make a compressed copy of the SQLite database. SQLite databases can be copied directly when connection is idle:
```bash
# Ensure backups folder exists
mkdir -p data/backups/

# Copy database with YYYYMMDD timestamp
cp data/sqlite/entertainment.db data/backups/entertainment_db_backup_$(date +%Y%m%d).db

# Keep only the last 4 backups (delete older)
find data/backups/ -name "entertainment_db_backup_*.db" -mtime +30 -delete
```

### Feed Review
List all configured feeds in EIP database and check their statuses:
```bash
python -c "from src.database.database import SessionLocal; from src.models.source import Source; db=SessionLocal(); [print(f'Name: {s.name:<20} | Domain: {s.domain:<20} | Enabled: {s.enabled}') for s in db.query(Source).all()]; db.close()"
```

### Dead Feed Review
Query and print all sources currently disabled due to consecutive failures:
```bash
python -c "from src.database.database import SessionLocal; from src.models.source import Source; db=SessionLocal(); [print(f'Dead Feed: {s.name:<20} | Failed: {s.last_failed_fetch} | Reason: {s.disabled_reason}') for s in db.query(Source).filter_by(enabled=False).all()]; db.close()"
```

### Metrics Review
List all system metrics for the past 7 days to review application loads:
```bash
python -c "import json; from src.database.database import SessionLocal; from src.services.metrics_service import MetricsService; db=SessionLocal(); print(json.dumps(MetricsService().daily_metrics_summary(db), indent=2)); db.close()"
```

---

## 3. Monthly Operations

### Dependency Updates
Check and apply updates for Python virtual environment packages:
```bash
# Activate environment
source .venv/bin/activate

# Check outdated packages
pip list --outdated

# Update critical packages and regenerate requirements
pip install --upgrade pip
pip install --upgrade apscheduler sqlalchemy aiohttp pydantic rapidfuzz
pip freeze > requirements.txt

# Restart EIP
sudo systemctl restart eip.service
```

### Server Updates
Apply security updates to the Oracle Linux server kernel and tools:
```bash
# Update installed packages
sudo dnf upgrade -y

# Restart server if kernel was updated
sudo reboot
```
*Note: Make sure to check EIP logs via `journalctl -u eip.service -f` immediately after server reboots to confirm auto-restart succeeded.*
