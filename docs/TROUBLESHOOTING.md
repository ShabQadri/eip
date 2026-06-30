# Entertainment Intelligence Platform (EIP) – Troubleshooting Guide

This guide provides diagnostics and resolutions for common issues encountered during EIP operations.

---

## 1. Service Won't Start

### Symptoms:
* Running `sudo systemctl start eip.service` succeeds, but status immediately becomes `failed` or `inactive`.
* Logs show `sys.exit(1)` or traceback during startup.

### Diagnostics:
Check the logs using journalctl:
```bash
journalctl -u eip.service -n 50 --no-pager
```
Identify the failure reason in self-test:
* **Database connection failed**: Check that `DATABASE_URL` path in `.env` exists and is writeable.
* **Feed configuration JSON invalid**: A JSON config file has syntax errors. Validate them:
  ```bash
  python -m json.tool data/events/alias_rules.json
  python -m json.tool data/events/franchise_rules.json
  python -m json.tool data/events/ignore_titles.json
  python -m json.tool data/feeds/editorial_rules.json
  ```
* **Telegram credentials missing/invalid**: Make sure token and channel ID are present in `.env` and token format has `:` delimiter.

---

## 2. Telegram Not Sending

### Symptoms:
* Scheduler jobs run, but messages are not published.
* Logs contain error message: `TelegramService sync wrapper error` or `telegram_failures` metrics count is increasing.

### Diagnostics & Resolution:
1. Verify token format and channel ID:
   ```bash
   cat .env | grep TELEGRAM
   ```
2. Manually test Telegram API using a curl command:
   ```bash
   # Replace BOT_TOKEN and CHANNEL_ID with actual values
   curl -X POST "https://api.telegram.org/bot<BOT_TOKEN>/sendMessage" \
        -d "chat_id=<CHANNEL_ID>" \
        -d "text=Test connection message"
   ```
   * If Telegram returns `401 Unauthorized` or `404 Not Found`: the bot token is invalid.
   * If Telegram returns `400 Bad Request`: the bot is not added as an administrator to the target channel, or the channel ID is incorrect.
   * If curl fails to connect: DNS issues or firewall blocking internet access on the Oracle instance.

---

## 3. Scheduler Stopped

### Symptoms:
* Daily digests or breaking alerts are not generating.
* Health check returns `"scheduler": {"status": "critical", "details": {"running": false}}`.

### Resolution:
1. Check systemd daemon logs for unhandled scheduler crash:
   ```bash
   journalctl -u eip.service | grep -i scheduler
   ```
2. Re-trigger scheduler start by restarting service:
   ```bash
   sudo systemctl restart eip.service
   ```

---

## 4. Database Locked

### Symptoms:
* Traceback shows `sqlite3.OperationalError: database is locked`.
* Database operations time out.

### Diagnostics & Resolution:
SQLite only allows one write transaction at a time. If a process hangs during a write operation, the database remains locked:
1. Identify other Python processes accessing the database:
   ```bash
   ps aux | grep python
   ```
2. Kill zombie Python processes holding lock handles:
   ```bash
   # Replaced PID with the process id identified from above
   kill -9 <PID>
   # OR kill all Python instances (WARNING: this stops EIP service as well)
   killall -9 python3
   ```
3. Restart the service:
   ```bash
   sudo systemctl restart eip.service
   ```

---

## 5. Feed Failures

### Symptoms:
* Logs show warning: `Failed to fetch feed` or metrics `feeds_failed` are high.
* Feeds are disabled with reason `5 consecutive failures`.

### Diagnostics:
Check if the RSS feeds are accessible from the server:
```bash
# Extract URL and query it using curl
curl -I "https://variety.com/feed/"
```
* If curl returns HTTP `403` or `401`: the source has blocked server IP or requires User-Agent headers.
* If feed is dead and must be re-enabled:
  ```bash
  python -c "from src.database.database import SessionLocal; from src.models.source import Source; db=SessionLocal(); s=db.query(Source).filter_by(name='Variety').first(); s.enabled=True; s.consecutive_failures=0; s.disabled_reason=None; db.commit(); db.close()"
  ```

---

## 6. Memory Issues

### Symptoms:
* Server becomes unresponsive.
* Logs show `Out of memory: Kill process` or EIP dies randomly.

### Diagnostics & Resolution:
SQLite and EIP are designed to run on Oracle Free Tier (1 GB RAM). Memory leaks can be diagnosed by checking memory usage:
1. Query EIP process memory stats:
   ```bash
   python -c "from src.services.health_service import get_memory_usage_mb; print(f'RAM Usage: {get_memory_usage_mb():.2f} MB')"
   ```
2. Ensure you are committing transactions and closing sessions inside jobs.
3. Configure systemd memory limit. Edit `/etc/systemd/system/eip.service`:
   ```ini
   [Service]
   ...
   MemoryMax=256M
   MemoryLimit=256M
   ```
   Save and run `sudo systemctl daemon-reload && sudo systemctl restart eip.service`.

---

## 7. Disk Full

### Symptoms:
* SQLite write operations fail with `sqlite3.OperationalError: disk I/O error` or `no space left on device`.
* App fails to write logs.

### Diagnostics & Resolution:
1. Check disk space:
   ```bash
   df -h
   ```
2. Check size of EIP application folder:
   ```bash
   du -sh /var/www/eip/data/*
   ```
3. Run the EIP cleanup job manually to free up retention space:
   ```bash
   python -c "from src.database.database import SessionLocal; from src.services.scheduler_service import SchedulerService; db=SessionLocal(); SchedulerService().run_cleanup_job(); db.close()"
   ```
4. Clear system logs or temporary files if necessary:
   ```bash
   sudo journalctl --vacuum-time=7d
   ```

---

## 8. Failed Deployment

### Symptoms:
* Code was updated, but the new version fails or runs old logic.
* Database is corrupted or out of sync.

### Resolution:
Perform a full clean deploy:
```bash
# Stop application
sudo systemctl stop eip.service

# Pull code
git pull origin main

# Reinstall clean packages
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Reset DB schema if migrations failed
python scripts/init_db.py

# Restart service
sudo systemctl start eip.service
```
