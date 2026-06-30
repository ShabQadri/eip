#!/usr/bin/env python
"""
EIP Management Command Line Interface (CLI).
Provides administrative commands for EIP database, health, metrics, and jobs execution.
"""

import os
import sys
import argparse
import json
import shutil
import asyncio
from datetime import datetime

# Add current directory to path to support absolute imports
sys.path.insert(0, os.getcwd())

# Configure basic logging for CLI commands
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("eip.manage")

from src.database.database import SessionLocal
from src.services.health_service import HealthService, get_memory_usage_mb, get_db_size_mb
from src.services.metrics_service import MetricsService
from src.services.scheduler_service import SchedulerService
from src.feeds.collection_service import CollectionService

# ANSI terminal formatting colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def print_success(message: str) -> None:
    try:
        print(f"{COLOR_GREEN}{COLOR_BOLD}✔ SUCCESS:{COLOR_RESET} {message}")
    except UnicodeEncodeError:
        print(f"{COLOR_GREEN}{COLOR_BOLD}[SUCCESS]:{COLOR_RESET} {message}")

def print_warning(message: str) -> None:
    try:
        print(f"{COLOR_YELLOW}{COLOR_BOLD}⚠ WARNING:{COLOR_RESET} {message}")
    except UnicodeEncodeError:
        print(f"{COLOR_YELLOW}{COLOR_BOLD}[WARNING]:{COLOR_RESET} {message}")

def print_error(message: str) -> None:
    try:
        print(f"{COLOR_RED}{COLOR_BOLD}✘ ERROR:{COLOR_RESET} {message}", file=sys.stderr)
    except UnicodeEncodeError:
        print(f"{COLOR_RED}{COLOR_BOLD}[ERROR]:{COLOR_RESET} {message}", file=sys.stderr)

def print_header(title: str) -> None:
    print(f"\n{COLOR_BLUE}{COLOR_BOLD}=== {title} ==={COLOR_RESET}\n")

# Command functions
def cmd_health() -> int:
    print_header("System Health Check")
    db = SessionLocal()
    try:
        hs = HealthService()
        health = hs.get_system_health(db)
        
        status = health["status"]
        if status == "healthy":
            print(f"Overall Status: {COLOR_GREEN}{COLOR_BOLD}HEALTHY{COLOR_RESET}")
        elif status == "warning":
            print(f"Overall Status: {COLOR_YELLOW}{COLOR_BOLD}WARNING{COLOR_RESET}")
        else:
            print(f"Overall Status: {COLOR_RED}{COLOR_BOLD}CRITICAL{COLOR_RESET}")
            
        print("\nDetails:")
        print(json.dumps(health["details"], indent=2))
        
        db.close()
        return 0 if status in {"healthy", "warning"} else 1
    except Exception as e:
        print_error(f"Failed to check health status: {e}")
        db.close()
        return 1

def cmd_admin_report() -> int:
    print_header("Daily Admin Report")
    db = SessionLocal()
    try:
        hs = HealthService()
        report = hs.generate_daily_admin_report(db)
        
        # Render a clean, readable text table
        print(f"{COLOR_BOLD}{'Metric / Parameter':<25} | {'Value':<12}{COLOR_RESET}")
        print("-" * 42)
        
        status_color = COLOR_GREEN if report["system_status"] == "healthy" else (COLOR_YELLOW if report["system_status"] == "warning" else COLOR_RED)
        print(f"{'System Status':<25} | {status_color}{report['system_status']}{COLOR_RESET}")
        print(f"{'Feeds Processed':<25} | {report['feeds_processed']}")
        print(f"{'Articles Fetched':<25} | {report['articles_fetched']}")
        print(f"{'Events Created':<25} | {report['events_created']}")
        print(f"{'Digests Sent':<25} | {report['digests_sent']}")
        print(f"{'Breaking Alerts Sent':<25} | {report['breaking_alerts_sent']}")
        print(f"{'Telegram Failures':<25} | {report['telegram_failures']}")
        print(f"{'Scheduler Failures':<25} | {report['scheduler_failures']}")
        print(f"{'Dead Feeds':<25} | {report['dead_feeds']}")
        print(f"{'Database Size (MB)':<25} | {report['database_size_mb']:.2f} MB")
        print(f"{'Memory Usage (MB)':<25} | {report['memory_usage_mb']:.2f} MB")
        print(f"{'Active Feeds':<25} | {report['active_feeds']}")
        
        db.close()
        return 0
    except Exception as e:
        print_error(f"Failed to generate admin report: {e}")
        db.close()
        return 1

def cmd_metrics() -> int:
    print_header("Daily Metrics Summary")
    db = SessionLocal()
    try:
        ms = MetricsService()
        summary = ms.daily_metrics_summary(db)
        print(json.dumps(summary, indent=2))
        db.close()
        return 0
    except Exception as e:
        print_error(f"Failed to load daily metrics: {e}")
        db.close()
        return 1

def cmd_morning_digest() -> int:
    print_header("Running Morning Digest Pipeline")
    try:
        # Reset SchedulerService singleton just in case
        SchedulerService._instance = None
        sched = SchedulerService()
        sched.run_morning_digest_job()
        print_success("Morning digest pipeline job completed successfully.")
        return 0
    except Exception as e:
        print_error(f"Morning digest pipeline job failed: {e}")
        return 1

def cmd_evening_digest() -> int:
    print_header("Running Evening Digest Pipeline")
    try:
        SchedulerService._instance = None
        sched = SchedulerService()
        sched.run_evening_digest_job()
        print_success("Evening digest pipeline job completed successfully.")
        return 0
    except Exception as e:
        print_error(f"Evening digest pipeline job failed: {e}")
        return 1

def cmd_breaking_check() -> int:
    print_header("Running Breaking Alert Check")
    try:
        SchedulerService._instance = None
        sched = SchedulerService()
        sched.run_breaking_alert_job()
        print_success("Breaking alert check completed successfully.")
        return 0
    except Exception as e:
        print_error(f"Breaking alert check job failed: {e}")
        return 1

def cmd_collect_feeds() -> int:
    print_header("Running Feed Collection Sweep")
    db = SessionLocal()
    try:
        coll = CollectionService()
        # collect_all is async
        result = asyncio.run(coll.collect_all(db))
        db.commit()
        
        print_success("Feed collection completed successfully.")
        print(f"Feeds processed: {result.feeds_processed}")
        print(f"Feeds succeeded: {result.feeds_succeeded}")
        print(f"Feeds failed:    {result.feeds_failed}")
        print(f"Articles stored: {result.articles_stored}")
        db.close()
        return 0
    except Exception as e:
        print_error(f"Feed collection job failed: {e}")
        db.close()
        return 1

def cmd_scheduler_status() -> int:
    print_header("Scheduler Status Check")
    try:
        hs = HealthService()
        status = hs.get_scheduler_health()
        
        if status["status"] == "healthy":
            print(f"Status: {COLOR_GREEN}{COLOR_BOLD}RUNNING{COLOR_RESET}")
            print(f"Jobs registered: {status['details']['job_count']}")
        else:
            print(f"Status: {COLOR_RED}{COLOR_BOLD}STOPPED / INACTIVE{COLOR_RESET}")
            print(f"Details: {status['details']['error']}")
            
        return 0 if status["status"] == "healthy" else 1
    except Exception as e:
        print_error(f"Failed to check scheduler status: {e}")
        return 1

def cmd_database_size() -> int:
    print_header("Database Size Diagnostics")
    try:
        size = get_db_size_mb()
        print(f"Database Path: {COLOR_BOLD}{SessionLocal().bind.url.database}{COLOR_RESET}")
        print(f"Size:          {COLOR_GREEN}{COLOR_BOLD}{size:.2f} MB{COLOR_RESET} ({int(size * 1024 * 1024)} bytes)")
        return 0
    except Exception as e:
        print_error(f"Failed to retrieve database size: {e}")
        return 1

def cmd_backup_db() -> int:
    print_header("Creating Database Backup")
    try:
        # Determine paths
        db_url = SessionLocal().bind.url.database
        if not db_url or db_url == ":memory:":
            print_error("Cannot backup an in-memory database.")
            return 1
            
        # Ensure backups folder exists
        backup_dir = os.path.join(os.getcwd(), "data", "backups")
        os.makedirs(backup_dir, exist_ok=True)
        
        # Build destination backup file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = os.path.join(backup_dir, f"entertainment_backup_{timestamp}.db")
        
        # Perform safe copy
        shutil.copy(db_url, backup_file)
        
        print_success(f"Database backed up successfully to:\n{backup_file}")
        return 0
    except Exception as e:
        print_error(f"Database backup failed: {e}")
        return 1

# Main entrypoint
def main() -> None:
    parser = argparse.ArgumentParser(
        description="EIP Management Command CLI.",
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    # Subcommands
    subparsers.add_parser("health", help="Check overview status of database, scheduler, telegram, and feeds.")
    subparsers.add_parser("admin-report", help="Generate daily diagnostics statistics summary.")
    subparsers.add_parser("metrics", help="Print recent daily metrics summary.")
    subparsers.add_parser("morning-digest", help="Manually run the morning digest pipeline sweep.")
    subparsers.add_parser("evening-digest", help="Manually run the evening digest pipeline sweep.")
    subparsers.add_parser("breaking-check", help="Manually check and alert on recent breaking news events.")
    subparsers.add_parser("collect-feeds", help="Execute an RSS feed sweep collection manually.")
    subparsers.add_parser("scheduler-status", help="Verify if background scheduler execution is active.")
    subparsers.add_parser("database-size", help="Query physical SQLite file size on disk.")
    subparsers.add_parser("backup-db", help="Create a time-stamped backup of the database file.")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    command_mapping = {
        "health": cmd_health,
        "admin-report": cmd_admin_report,
        "metrics": cmd_metrics,
        "morning-digest": cmd_morning_digest,
        "evening-digest": cmd_evening_digest,
        "breaking-check": cmd_breaking_check,
        "collect-feeds": cmd_collect_feeds,
        "scheduler-status": cmd_scheduler_status,
        "database-size": cmd_database_size,
        "backup-db": cmd_backup_db
    }
    
    exit_code = command_mapping[args.command]()
    sys.exit(exit_code)

if __name__ == "__main__":
    main()
