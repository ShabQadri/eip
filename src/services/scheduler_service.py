import logging
import asyncio
import concurrent.futures
from typing import Optional
from datetime import datetime, timezone, timedelta
from apscheduler.schedulers.background import BackgroundScheduler
from src.feeds.collection_service import CollectionService
from src.processing.events.event_service import EventService
from src.processing.digests.digest_service import DigestService
from src.services.telegram_service import TelegramService
from src.processing.digests.telegram_formatter import TelegramFormatter
from src.models import Article, Event
from src.services.publication_service import PublicationService

logger = logging.getLogger("eip.scheduler_service")

class SchedulerService:
    """
    Scheduler Service coordinating EIP automatic job execution.
    Morning Digest: 08:00 local time
    Evening Digest: 20:00 local time
    Breaking Alerts check: every 10 minutes
    Cleanup task: 02:00 daily
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        collection_service: Optional[CollectionService] = None,
        event_service: Optional[EventService] = None,
        digest_service: Optional[DigestService] = None,
        telegram_service: Optional[TelegramService] = None,
        telegram_formatter: Optional[TelegramFormatter] = None,
        publication_service: Optional[PublicationService] = None
    ) -> None:
        if hasattr(self, "initialized") and self.initialized:
            return
            
        self.collection_service = collection_service or CollectionService()
        self.event_service = event_service or EventService()
        self.telegram_formatter = telegram_formatter or TelegramFormatter()
        self.telegram_service = telegram_service or TelegramService()
        self.publication_service = publication_service or PublicationService()

        if not digest_service:
            from src.processing.digests.breaking_detector import BreakingDetector
            from src.processing.digests.digest_selector import DigestSelector
            from src.processing.digests.digest_formatter import DigestFormatter
            self.digest_service = DigestService(
                breaking_detector=BreakingDetector(),
                digest_selector=DigestSelector(publication_service=self.publication_service),
                digest_formatter=DigestFormatter(),
                telegram_formatter=self.telegram_formatter
            )
        else:
            self.digest_service = digest_service
        
        self.scheduler = BackgroundScheduler()
        self.initialized = True

    def _run_sync(self, coro):
        """Helper to run async coroutines synchronously in both sync and async event loop contexts."""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)

    async def _run_digest_pipeline_async(self, digest_type: str) -> None:
        from src.database.database import SessionLocal
        db = SessionLocal()
        import time as time_metric
        start_time = time_metric.perf_counter()
        try:
            logger.info(f"Starting {digest_type} digest pipeline collection...")
            # 1. Collect feeds
            await self.collection_service.collect_all(db)
            
            # 2. Build events
            new_articles = db.query(Article).filter_by(status="new").all()
            for art in new_articles:
                try:
                    self.event_service.process_article(db, art)
                    art.status = "processed"
                except Exception as e:
                    logger.error(f"Error processing article {art.id} in digest scheduler: {e}")
            db.commit()

            # 3. Generate digest
            digest_text = self.digest_service.generate_digest(db, digest_type=digest_type, telegram_safe=True)

            # 4. Publish Telegram digest
            if "No major entertainment developments at this time." not in digest_text:
                res = self.telegram_service.send_digest(digest_text)
                if res.get("success"):
                    # Mark selected events as published
                    post_type = "DIGEST_MORNING" if digest_type == "morning" else "DIGEST_EVENING"
                    events = self.digest_service.digest_selector.select_events_for_digest(db)
                    for event in events:
                        msg_id = str(res.get("message_id")) if res.get("message_id") is not None else None
                        self.publication_service.mark_published(
                            db, 
                            event.id, 
                            "TELEGRAM", 
                            post_type, 
                            external_id=msg_id,
                            metadata={"message_id": msg_id} if msg_id else {}
                        )
                    db.commit()
                    logger.info(f"Published {digest_type} digest successfully.")

                    # Record digests_sent metric
                    try:
                        from src.services.metrics_service import MetricsService
                        MetricsService().increment(db, "digests_sent")
                        db.commit()
                    except Exception:
                        pass
                else:
                    logger.error(f"Failed to publish {digest_type} digest: {res.get('error')}")
            else:
                logger.info(f"No events for {digest_type} digest. Skipping Telegram publish.")

            # Record processing time
            duration_ms = (time_metric.perf_counter() - start_time) * 1000
            try:
                from src.services.metrics_service import MetricsService
                MetricsService().record_metric(db, "processing_time_ms", duration_ms)
                db.commit()
            except Exception:
                pass

        except Exception as e:
            db.rollback()
            logger.error(f"Exception in {digest_type} digest pipeline: {e}")
            try:
                from src.services.metrics_service import MetricsService
                MetricsService().increment(db, "scheduler_failures")
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

    async def _run_breaking_alert_pipeline_async(self) -> None:
        from src.database.database import SessionLocal
        db = SessionLocal()
        import time as time_metric
        start_time = time_metric.perf_counter()
        try:
            logger.info("Starting breaking alert pipeline collection...")
            # 1. Collect feeds
            await self.collection_service.collect_all(db)
            
            # 2. Build events
            new_articles = db.query(Article).filter_by(status="new").all()
            for art in new_articles:
                try:
                    self.event_service.process_article(db, art)
                    art.status = "processed"
                except Exception as e:
                    logger.error(f"Error processing article {art.id} in breaking scheduler: {e}")
            db.commit()

            # 3. Detect breaking events
            breaking_events = self.digest_service.get_breaking_events(db)

            # 4. Publish alerts (prevent duplicate publication)
            for event in breaking_events:
                if self.publication_service.is_published(db, event.id, "TELEGRAM", "BREAKING_ALERT"):
                    continue
                
                alert_text = self.telegram_formatter.format_breaking_alert(event)
                res = self.telegram_service.send_breaking_alert(alert_text)
                if res.get("success"):
                    msg_id = str(res.get("message_id")) if res.get("message_id") is not None else None
                    self.publication_service.mark_published(
                        db, 
                        event.id, 
                        "TELEGRAM", 
                        "BREAKING_ALERT", 
                        external_id=msg_id,
                        metadata={"message_id": msg_id} if msg_id else {}
                    )
                    db.commit()
                    logger.info(f"Published breaking alert for event {event.id} ({event.canonical_title})")

                    # Record breaking_alerts_sent metric
                    try:
                        from src.services.metrics_service import MetricsService
                        MetricsService().increment(db, "breaking_alerts_sent")
                        db.commit()
                    except Exception:
                        pass
                else:
                    logger.error(f"Failed to publish breaking alert for event {event.id}: {res.get('error')}")

            # Record processing time
            duration_ms = (time_metric.perf_counter() - start_time) * 1000
            try:
                from src.services.metrics_service import MetricsService
                MetricsService().record_metric(db, "processing_time_ms", duration_ms)
                db.commit()
            except Exception:
                pass

        except Exception as e:
            db.rollback()
            logger.error(f"Exception in breaking alert pipeline: {e}")
            try:
                from src.services.metrics_service import MetricsService
                MetricsService().increment(db, "scheduler_failures")
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

    def run_morning_digest_job(self) -> None:
        logger.info("Running morning digest job...")
        self._run_sync(self._run_digest_pipeline_async("morning"))

    def run_evening_digest_job(self) -> None:
        logger.info("Running evening digest job...")
        self._run_sync(self._run_digest_pipeline_async("evening"))

    def run_breaking_alert_job(self) -> None:
        logger.info("Running breaking alert check job...")
        self._run_sync(self._run_breaking_alert_pipeline_async())

    def run_cleanup_job(self) -> None:
        logger.info("Running daily cleanup job...")
        from src.database.database import SessionLocal
        db = SessionLocal()
        try:
            from src.models.settings import Settings
            settings_rec = db.query(Settings).first()
            if not settings_rec:
                logger.warning("No settings record found. Skipping cleanup.")
                return

            # 1. Cleanup old articles
            article_cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=settings_rec.article_retention_days)
            deleted_articles = db.query(Article).filter(Article.created_at < article_cutoff).delete()
            db.commit()
            logger.info(f"Cleaned up {deleted_articles} old articles.")

            # 2. Cleanup old images
            from src.config.settings import settings as app_settings
            import time
            image_dir = app_settings.IMAGE_DIR
            deleted_images = 0
            if image_dir.exists():
                now_secs = time.time()
                image_retention_secs = settings_rec.image_retention_days * 24 * 3600
                for item in image_dir.iterdir():
                    if item.is_file():
                        if now_secs - item.stat().st_mtime > image_retention_secs:
                            try:
                                item.unlink()
                                deleted_images += 1
                            except Exception as e:
                                logger.error(f"Failed to delete old image file {item}: {e}")
            logger.info(f"Cleaned up {deleted_images} old image files.")

            # 3. Cleanup old logs
            log_dir = app_settings.LOG_DIR
            deleted_logs = 0
            if log_dir.exists():
                now_secs = time.time()
                log_retention_secs = settings_rec.log_retention_days * 24 * 3600
                for item in log_dir.iterdir():
                    if item.is_file():
                        if now_secs - item.stat().st_mtime > log_retention_secs:
                            try:
                                item.unlink()
                                deleted_logs += 1
                            except Exception as e:
                                logger.error(f"Failed to delete old log file {item}: {e}")
            logger.info(f"Cleaned up {deleted_logs} old log files.")

            # 4. Cleanup old system metrics
            from src.models.system_metric import SystemMetric
            retention_days = getattr(settings_rec, "metric_retention_days", 365)
            metric_cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
            deleted_metrics = db.query(SystemMetric).filter(SystemMetric.created_at < metric_cutoff).delete()
            db.commit()
            logger.info(f"Cleaned up {deleted_metrics} old system metrics.")

        except Exception as e:
            db.rollback()
            logger.error(f"Exception in cleanup job: {e}")
        finally:
            db.close()

    def run_heartbeat_job(self) -> None:
        """
        Job to collect, persist, and log system heartbeat metrics.
        """
        logger.info("Running system heartbeat job...")
        from src.database.database import SessionLocal
        from src.services.metrics_service import MetricsService
        from src.services.health_service import get_memory_usage_mb, get_db_size_mb
        from src.models.source import Source
        
        db = SessionLocal()
        try:
            # Collect
            memory = get_memory_usage_mb()
            db_size = get_db_size_mb()
            active_feeds_count = db.query(Source).filter_by(enabled=True).count()
            
            ms = MetricsService()
            ms.record_metric(db, "system_heartbeat", 1.0, aggregation_type="COUNTER", source="SchedulerService")
            ms.record_metric(db, "memory_usage_mb", memory, aggregation_type="GAUGE", source="SchedulerService")
            ms.record_metric(db, "database_size_mb", db_size, aggregation_type="GAUGE", source="SchedulerService")
            ms.record_metric(db, "active_feeds", active_feeds_count, aggregation_type="GAUGE", source="SchedulerService")
            ms.record_metric(db, "scheduler_running", 1.0, aggregation_type="GAUGE", source="SchedulerService")
            db.commit()
            
            logger.info(
                f"Heartbeat:\nmemory={memory:.2f} MB\ndb={db_size:.2f} MB\nfeeds={active_feeds_count}"
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Exception in heartbeat job: {e}")
            try:
                ms = MetricsService()
                ms.increment(db, "scheduler_failures", source="SchedulerService")
                db.commit()
            except Exception:
                pass
        finally:
            db.close()

    def start(self) -> None:
        if self.scheduler.running:
            logger.warning("Scheduler is already running.")
            return

        self.scheduler.add_job(
            self.run_morning_digest_job,
            trigger="cron",
            hour=8,
            minute=0,
            id="morning_digest"
        )
        self.scheduler.add_job(
            self.run_evening_digest_job,
            trigger="cron",
            hour=20,
            minute=0,
            id="evening_digest"
        )
        self.scheduler.add_job(
            self.run_breaking_alert_job,
            trigger="interval",
            minutes=10,
            id="breaking_alerts"
        )
        self.scheduler.add_job(
            self.run_cleanup_job,
            trigger="cron",
            hour=2,
            minute=0,
            id="cleanup"
        )
        self.scheduler.add_job(
            self.run_heartbeat_job,
            trigger="interval",
            minutes=10,
            id="system_heartbeat"
        )

        self.scheduler.start()
        logger.info("Scheduler started successfully.")

    def shutdown(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Scheduler shut down successfully.")
