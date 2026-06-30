"""
Tests for EIP Management CLI (manage.py).
"""

import sys
import os
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy.orm import Session

# Add current directory to path
sys.path.insert(0, os.getcwd())

import manage
from src.database.database import SessionLocal

@pytest.fixture(name="db_session")
def fixture_db_session() -> Session:
    """Creates a temporary in-memory database session for CLI testing."""
    from sqlalchemy import create_engine
    from src.database.base import Base
    
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    from sqlalchemy.orm import sessionmaker
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    from src.models.settings import Settings
    settings_rec = Settings(
        article_retention_days=90,
        image_retention_days=180,
        log_retention_days=30,
        breaking_threshold=80,
        digest_threshold=60,
        max_articles_per_digest=12,
        cleanup_hour=2,
        keep_images=True,
        metric_retention_days=365
    )
    session.add(settings_rec)
    session.commit()
    
    yield session
    session.close()
    engine.dispose()

def test_health_command(db_session: Session) -> None:
    """Verify that health command completes successfully when database is responsive."""
    with patch("manage.SessionLocal", return_value=db_session), \
         patch("src.services.health_service.HealthService.get_system_health") as mock_health:
        mock_health.return_value = {"status": "healthy", "details": {}}
        
        exit_code = manage.cmd_health()
        assert exit_code == 0
        mock_health.assert_called_once()

    # Fail path
    with patch("manage.SessionLocal", return_value=db_session), \
         patch("src.services.health_service.HealthService.get_system_health") as mock_health:
        mock_health.return_value = {"status": "critical", "details": {}}
        
        exit_code = manage.cmd_health()
        assert exit_code == 1

def test_admin_report_command(db_session: Session) -> None:
    """Verify that admin report command executes cleanly."""
    with patch("manage.SessionLocal", return_value=db_session), \
         patch("src.services.health_service.HealthService.generate_daily_admin_report") as mock_report:
        mock_report.return_value = {
            "system_status": "healthy",
            "feeds_processed": 0,
            "articles_fetched": 0,
            "events_created": 0,
            "digests_sent": 0,
            "breaking_alerts_sent": 0,
            "telegram_failures": 0,
            "scheduler_failures": 0,
            "dead_feeds": 0,
            "database_size_mb": 0.0,
            "memory_usage_mb": 0.0,
            "active_feeds": 0
        }
        
        exit_code = manage.cmd_admin_report()
        assert exit_code == 0
        mock_report.assert_called_once()

def test_metrics_command(db_session: Session) -> None:
    """Verify that metrics command formats and outputs metrics summary."""
    with patch("manage.SessionLocal", return_value=db_session), \
         patch("src.services.metrics_service.MetricsService.daily_metrics_summary") as mock_metrics:
        mock_metrics.return_value = {"feeds_processed": 5}
        
        exit_code = manage.cmd_metrics()
        assert exit_code == 0
        mock_metrics.assert_called_once()

def test_digest_jobs_commands() -> None:
    """Verify that morning/evening/breaking digest command functions execute the job runs."""
    with patch("src.services.scheduler_service.SchedulerService.run_morning_digest_job") as mock_job:
        exit_code = manage.cmd_morning_digest()
        assert exit_code == 0
        mock_job.assert_called_once()

    with patch("src.services.scheduler_service.SchedulerService.run_evening_digest_job") as mock_job:
        exit_code = manage.cmd_evening_digest()
        assert exit_code == 0
        mock_job.assert_called_once()

    with patch("src.services.scheduler_service.SchedulerService.run_breaking_alert_job") as mock_job:
        exit_code = manage.cmd_breaking_check()
        assert exit_code == 0
        mock_job.assert_called_once()

def test_collect_feeds_command(db_session: Session) -> None:
    """Verify that collect-feeds command triggers async collection runner."""
    from src.feeds.collection_service import CollectionResult
    res = CollectionResult(feeds_processed=2, feeds_succeeded=2, feeds_failed=0, articles_stored=5)
    
    with patch("manage.SessionLocal", return_value=db_session), \
         patch("src.feeds.collection_service.CollectionService.collect_all", return_value=res) as mock_collect:
        exit_code = manage.cmd_collect_feeds()
        assert exit_code == 0
        mock_collect.assert_called_once()

def test_scheduler_status_command() -> None:
    """Verify that scheduler-status command retrieves scheduler health."""
    with patch("src.services.health_service.HealthService.get_scheduler_health") as mock_health:
        mock_health.return_value = {"status": "healthy", "details": {"job_count": 5}}
        exit_code = manage.cmd_scheduler_status()
        assert exit_code == 0
        mock_health.assert_called_once()

        mock_health.return_value = {"status": "critical", "details": {"error": "Stopped"}}
        exit_code = manage.cmd_scheduler_status()
        assert exit_code == 1

def test_database_size_command() -> None:
    """Verify that database size command calculates database file size."""
    with patch("manage.get_db_size_mb", return_value=1.5):
        exit_code = manage.cmd_database_size()
        assert exit_code == 0

def test_backup_db_command() -> None:
    """Verify that backup command triggers database copy."""
    mock_session = MagicMock()
    mock_session.bind.url.database = "data/sqlite/entertainment.db"
    with patch("manage.SessionLocal", return_value=mock_session), \
         patch("shutil.copy") as mock_copy, \
         patch("os.makedirs") as mock_makedirs:
         
        exit_code = manage.cmd_backup_db()
        assert exit_code == 0
        mock_makedirs.assert_called_once()
        mock_copy.assert_called_once()

def test_main_cli_routing() -> None:
    """Verify that main routing correctly calls matching cmd functions."""
    with patch("sys.argv", ["manage.py", "health"]), \
         patch("manage.cmd_health", return_value=0) as mock_cmd:
        with pytest.raises(SystemExit) as exc_info:
            manage.main()
        assert exc_info.value.code == 0
        mock_cmd.assert_called_once()
