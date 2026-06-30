"""
Health check and startup verification service for EIP.
"""

import os
import sys
import platform
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from sqlalchemy import text
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.models.settings import Settings
from src.models.system_metric import SystemMetric
from src.models.published_post import PublishedPost
from src.models.source import Source
from src.services.metrics_service import MetricsService

logger = logging.getLogger("eip.health_service")

def get_memory_usage_mb() -> float:
    """
    Collects physical memory (RSS) usage of the current process in MB.
    Preferred order:
    1. psutil
    2. resource module (Unix)
    3. ctypes fallback (Windows)
    """
    # 1. psutil
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return float(process.memory_info().rss / 1024 / 1024)
    except ImportError:
        pass
    except Exception:
        pass

    # 2. resource module (Linux/macOS)
    try:
        import resource
        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        # ru_maxrss is in KB on Linux, bytes on macOS
        if platform.system() == "Darwin":
            return float(usage / 1024 / 1024)
        else:
            return float(usage / 1024)
    except ImportError:
        pass
    except Exception:
        pass

    # 3. ctypes fallback (Windows)
    try:
        import ctypes
        from ctypes import wintypes
        
        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]
            
        GetProcessMemoryInfo = ctypes.windll.psapi.GetProcessMemoryInfo
        GetCurrentProcess = ctypes.windll.kernel32.GetCurrentProcess
        
        process = GetCurrentProcess()
        counters = PROCESS_MEMORY_COUNTERS()
        counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
        
        if GetProcessMemoryInfo(process, ctypes.byref(counters), counters.cb):
            return float(counters.WorkingSetSize / 1024 / 1024)
    except Exception:
        pass

    return 0.0

def get_db_size_mb() -> float:
    """
    Returns the size of the SQLite database file on disk in MB.
    """
    try:
        url = settings.DATABASE_URL
        if url.startswith("sqlite:///"):
            path = url.replace("sqlite:///", "")
            # Clean up Windows absolute path format if needed
            if path.startswith("/") and len(path) > 2 and path[2] == ":":
                path = path[1:]
            if os.path.exists(path):
                return float(os.path.getsize(path) / 1024 / 1024)
    except Exception as e:
        logger.error(f"Error checking database size: {e}")
    return 0.0

class HealthService:
    """
    Performs system diagnostics, startup self-tests, and admin reporting.
    """
    def get_database_health(self, session: Session) -> Dict[str, Any]:
        """
        Verifies database connectivity and existence of core tables.
        """
        try:
            # Test query
            session.execute(text("SELECT 1"))
            
            # Check tables exist by trying to query them
            session.query(SystemMetric).limit(1).all()
            session.query(PublishedPost).limit(1).all()
            
            return {
                "status": "healthy",
                "details": {
                    "connection": "ok",
                    "tables": {
                        "system_metrics": "ok",
                        "published_posts": "ok"
                    }
                }
            }
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                "status": "critical",
                "details": {
                    "error": str(e)
                }
            }

    def get_scheduler_health(self) -> Dict[str, Any]:
        """
        Checks if APScheduler is running.
        """
        try:
            from src.services.scheduler_service import SchedulerService
            # SchedulerService is a singleton class
            svc = SchedulerService()
            if svc.scheduler and svc.scheduler.running:
                return {
                    "status": "healthy",
                    "details": {
                        "running": True,
                        "job_count": len(svc.scheduler.get_jobs())
                    }
                }
            else:
                return {
                    "status": "critical",
                    "details": {
                        "running": False,
                        "error": "Scheduler is not running or stopped."
                    }
                }
        except Exception as e:
            logger.error(f"Scheduler health check failed: {e}")
            return {
                "status": "critical",
                "details": {
                    "error": str(e)
                }
            }

    def get_feed_health(self, session: Session) -> Dict[str, Any]:
        """
        Checks for dead/disabled feeds and general feed retrieval state.
        """
        try:
            total_feeds = session.query(Source).count()
            disabled_feeds = session.query(Source).filter_by(enabled=False).all()
            disabled_count = len(disabled_feeds)
            
            if disabled_count == 0:
                status = "healthy"
            elif 1 <= disabled_count <= 3:
                status = "warning"
            else:
                status = "critical"
                
            return {
                "status": status,
                "details": {
                    "total_feeds": total_feeds,
                    "enabled_feeds": total_feeds - disabled_count,
                    "disabled_feeds": disabled_count,
                    "dead_feeds_list": [
                        {
                            "name": s.name, 
                            "disabled_reason": s.disabled_reason or "unknown",
                            "disabled_at": s.disabled_at.isoformat() if s.disabled_at else None
                        } for s in disabled_feeds
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Feed health check failed: {e}")
            return {
                "status": "critical",
                "details": {
                    "error": str(e)
                }
            }

    def get_telegram_health(self) -> Dict[str, Any]:
        """
        Validates Telegram bot token and channel credentials presence and format.
        """
        token = settings.TELEGRAM_BOT_TOKEN
        channel = settings.TELEGRAM_CHANNEL_ID
        
        errors = []
        if not token:
            errors.append("TELEGRAM_BOT_TOKEN is missing or empty")
        elif ":" not in token:
            errors.append("TELEGRAM_BOT_TOKEN format is invalid (missing ':')")
            
        if not channel:
            errors.append("TELEGRAM_CHANNEL_ID is missing or empty")
            
        if errors:
            return {
                "status": "critical",
                "details": {
                    "errors": errors
                }
            }
            
        return {
            "status": "healthy",
            "details": {
                "token_format": "valid",
                "channel_id_present": "valid"
            }
        }

    def get_system_health(self, session: Session) -> Dict[str, Any]:
        """
        Aggregates health statuses across database, scheduler, feeds, and telegram.
        Status Priority: critical > warning > healthy.
        """
        db_h = self.get_database_health(session)
        sched_h = self.get_scheduler_health()
        feed_h = self.get_feed_health(session)
        tg_h = self.get_telegram_health()
        
        statuses = [db_h["status"], sched_h["status"], feed_h["status"], tg_h["status"]]
        
        if "critical" in statuses:
            status = "critical"
        elif "warning" in statuses:
            status = "warning"
        else:
            status = "healthy"
            
        return {
            "status": status,
            "details": {
                "database": db_h,
                "scheduler": sched_h,
                "feeds": feed_h,
                "telegram": tg_h
            }
        }

    def run_startup_self_test(self, session: Session) -> Dict[str, str]:
        """
        Runs critical startup self-tests. Raises ValueError or exits on failure.
        """
        results = {}
        
        # 1. Database Connection & Tables
        try:
            session.execute(text("SELECT 1"))
            results["database"] = "ok"
        except Exception as e:
            logger.critical("Database unavailable. Application shutdown.")
            raise RuntimeError(f"Database connection failed: {e}")
            
        try:
            session.query(SystemMetric).limit(1).all()
            results["metrics_table"] = "ok"
        except Exception as e:
            raise RuntimeError(f"Metrics table validation failed: {e}")
            
        try:
            session.query(PublishedPost).limit(1).all()
            results["publication_table"] = "ok"
        except Exception as e:
            raise RuntimeError(f"Publication table validation failed: {e}")

        # 2. Scheduler
        try:
            from src.services.scheduler_service import SchedulerService
            # Instantiate to confirm no dependency errors
            _ = SchedulerService()
            results["scheduler"] = "ok"
        except Exception as e:
            raise RuntimeError(f"Scheduler initialization failed: {e}")

        # 3. Feed Configuration files
        from src.config.settings import settings as app_settings
        project_root = app_settings.BASE_DIR
        
        configs = {
            "ignore_titles": project_root / "data" / "events" / "ignore_titles.json",
            "alias_rules": project_root / "data" / "events" / "alias_rules.json",
            "franchise_rules": project_root / "data" / "events" / "franchise_rules.json",
            "editorial_rules": project_root / "data" / "feeds" / "editorial_rules.json"
        }
        
        for name, path in configs.items():
            if not path.exists():
                raise FileNotFoundError(f"Feed configuration file missing: {path.name}")
            try:
                import json
                with open(path, "r", encoding="utf-8") as f:
                    json.load(f)
            except Exception as je:
                raise ValueError(f"Feed configuration JSON invalid: {path.name} ({je})")
        results["feed_configs"] = "ok"

        # 4. Telegram bot configurations
        tg_health = self.get_telegram_health()
        if tg_health["status"] == "critical":
            raise ValueError(f"Telegram configuration invalid: {tg_health['details']['errors']}")
        results["telegram"] = "ok"
        
        return results

    def generate_daily_admin_report(self, session: Session) -> Dict[str, Any]:
        """
        Generates summary metrics and health overview for administrative reporting.
        """
        health = self.get_system_health(session)
        summary = MetricsService().daily_metrics_summary(session)
        
        dead_feeds_count = session.query(Source).filter_by(enabled=False).count()
        active_feeds_count = session.query(Source).filter_by(enabled=True).count()
        db_size = get_db_size_mb()
        mem_usage = get_memory_usage_mb()
        
        return {
            "system_status": health["status"],
            "feeds_processed": summary.get("feeds_processed", 0),
            "articles_fetched": summary.get("articles_fetched", 0),
            "events_created": summary.get("events_created", 0),
            "digests_sent": summary.get("digests_sent", 0),
            "breaking_alerts_sent": summary.get("breaking_alerts_sent", 0),
            "telegram_failures": summary.get("telegram_failures", 0),
            "scheduler_failures": summary.get("scheduler_failures", 0),
            "dead_feeds": dead_feeds_count,
            "database_size_mb": float(round(db_size, 2)),
            "memory_usage_mb": float(round(mem_usage, 2)),
            "active_feeds": active_feeds_count
        }
