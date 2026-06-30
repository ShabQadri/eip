# Entertainment Intelligence Platform (EIP) – Rollback Procedure

This document contains copy-paste ready commands to revert EIP to a previous functional release in the event of an operational failure.

---

## 1. Stop EIP Service
Immediately stop the running application instance to prevent database writes or corrupted publishes:
```bash
# Stop eip background service
sudo systemctl stop eip.service
```

## 2. Revert Git Commit
Revert codebase changes back to a known-stable commit:
```bash
# Navigate to project root directory
cd /var/www/eip

# Check git release tags or commit history
git log --oneline -n 10

# Revert working tree to stable commit or tag (replace with stable commit hash or tag name)
git checkout stable-v1.0.0
# OR checkout specific commit hash
git reset --hard a1b2c3d4
```

## 3. Restore Database Backup
If schema corruption occurred or data was compromised, restore a previously created backup of the SQLite database:
```bash
# Verify existing backups directory
ls -la data/backups/

# Backup current corrupted database just in case
mv data/sqlite/entertainment.db data/sqlite/entertainment.db.corrupted

# Copy backup file back to active database file (replace with correct date)
cp data/backups/entertainment_db_backup_YYYYMMDD.db data/sqlite/entertainment.db

# Ensure correct file permissions
chmod 660 data/sqlite/entertainment.db
```

## 4. Restart EIP Service
Reload systemd configurations and start the application back up:
```bash
# Reload configurations
sudo systemctl daemon-reload

# Restart background service
sudo systemctl start eip.service
```

## 5. Verify Health Status
Verify that the service is running, and that all subsystems show "healthy" state:
```bash
# Verify systemd service status
sudo systemctl status eip.service

# Verify app health CLI
python -c "import json; from src.database.database import SessionLocal; from src.services.health_service import HealthService; db=SessionLocal(); print(json.dumps(HealthService().get_system_health(db), indent=2)); db.close()"

# Monitor logs
journalctl -u eip.service -f -n 50
```
If the health check returns `"status": "healthy"`, the rollback has succeeded.
