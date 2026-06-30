"""
Tests for HealthService and Step 7.2 diagnostics and production readiness checks.
"""

import os
import tempfile
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, mock_open
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from src.database.base import Base
from src.models.settings import Settings
from src.models.system_metric import SystemMetric
from src.models.published_post import PublishedPost
from src.models.source import Source
from src.services.health_service import HealthService, get_memory_usage_mb, get_db_size_mb
from src.services.scheduler_service import SchedulerService
from src.feeds.collection_service import CollectionService

@pytest.fixture(name="db_session")
def fixture_db_session() -> Session:
    """Fixture to build a temporary disk-based SQLite DB and return a session."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    engine = create_engine(f"sqlite:///{temp_db_path}")
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    Base.metadata.create_all(bind=engine)
    
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    
    # Seed default Settings
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
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

def test_health_status_priority(db_session: Session) -> None:
    """Test 1: Verify health levels priorities (critical > warning > healthy)."""
    hs = HealthService()

    # --- Case A: All healthy ---
    with patch.object(hs, "get_database_health", return_value={"status": "healthy"}), \
         patch.object(hs, "get_scheduler_health", return_value={"status": "healthy"}), \
         patch.object(hs, "get_feed_health", return_value={"status": "healthy"}), \
         patch.object(hs, "get_telegram_health", return_value={"status": "healthy"}):
        res = hs.get_system_health(db_session)
        assert res["status"] == "healthy"

    # --- Case B: Warning present ---
    with patch.object(hs, "get_database_health", return_value={"status": "healthy"}), \
         patch.object(hs, "get_scheduler_health", return_value={"status": "healthy"}), \
         patch.object(hs, "get_feed_health", return_value={"status": "warning"}), \
         patch.object(hs, "get_telegram_health", return_value={"status": "healthy"}):
        res = hs.get_system_health(db_session)
        assert res["status"] == "warning"

    # --- Case C: Critical and Warning present -> Critical wins ---
    with patch.object(hs, "get_database_health", return_value={"status": "critical"}), \
         patch.object(hs, "get_scheduler_health", return_value={"status": "healthy"}), \
         patch.object(hs, "get_feed_health", return_value={"status": "warning"}), \
         patch.object(hs, "get_telegram_health", return_value={"status": "healthy"}):
        res = hs.get_system_health(db_session)
        assert res["status"] == "critical"

def test_startup_self_test_failure(db_session: Session) -> None:
    """Test 2: Startup self-test failure logic and file config checks."""
    hs = HealthService()

    # Database fails
    mock_bad_db = MagicMock(spec=Session)
    mock_bad_db.execute.side_effect = Exception("DB Connection Refused")
    with pytest.raises(RuntimeError, match="Database connection failed"):
        hs.run_startup_self_test(mock_bad_db)

    # Missing config files
    with patch("pathlib.Path.exists", return_value=False):
        with pytest.raises(FileNotFoundError, match="Feed configuration file missing"):
            hs.run_startup_self_test(db_session)

    # Invalid JSON config file
    with patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data="invalid-json-{")):
        with pytest.raises(ValueError, match="Feed configuration JSON invalid"):
            hs.run_startup_self_test(db_session)

    # Invalid Telegram token
    with patch("pathlib.Path.exists", return_value=True), \
         patch("builtins.open", mock_open(read_data="{}")), \
         patch("src.config.settings.settings.TELEGRAM_BOT_TOKEN", "badtoken"):
        with pytest.raises(ValueError, match="Telegram configuration invalid"):
            hs.run_startup_self_test(db_session)

def test_heartbeat_job(db_session: Session) -> None:
    """Test 3: Heartbeat job stores all 5 required metrics in DB."""
    # Seed an active feed
    source = Source(
        id="src-hb-1",
        name="Variety",
        domain="variety.com",
        rss_url="https://variety.com/feed/",
        source_type="RSS",
        source_tier=1,
        policy="SUMMARY_ALLOWED",
        enabled=True
    )
    db_session.add(source)
    db_session.commit()

    scheduler_service = SchedulerService(
        collection_service=MagicMock(),
        event_service=MagicMock(),
        digest_service=MagicMock(),
        telegram_service=MagicMock(),
        telegram_formatter=MagicMock(),
        publication_service=MagicMock()
    )

    with patch("src.database.database.SessionLocal", return_value=db_session):
        scheduler_service.run_heartbeat_job()
        db_session.commit()

    # Query metrics recorded
    metrics = db_session.query(SystemMetric).all()
    names = {m.metric_name for m in metrics}
    
    assert "system_heartbeat" in names
    assert "memory_usage_mb" in names
    assert "database_size_mb" in names
    assert "active_feeds" in names
    assert "scheduler_running" in names

    heartbeat = db_session.query(SystemMetric).filter_by(metric_name="system_heartbeat").first()
    assert heartbeat.aggregation_type == "COUNTER"

    mem_usage = db_session.query(SystemMetric).filter_by(metric_name="memory_usage_mb").first()
    assert mem_usage.aggregation_type == "GAUGE"

def test_dead_feed_disabling(db_session: Session) -> None:
    """Test 4: Source is disabled on 5th failure and records dead_feeds_detected metric."""
    source = Source(
        id="src-failed-1",
        name="Variety Failed",
        domain="variety.com",
        rss_url="https://variety.com/failed/",
        source_type="RSS",
        source_tier=1,
        policy="SUMMARY_ALLOWED",
        enabled=True,
        consecutive_failures=4 # 4 existing failures
    )
    db_session.add(source)
    db_session.commit()

    coll = CollectionService()
    
    # Mock RSSFetcher to fail (return None content)
    with patch("src.feeds.rss_fetcher.RSSFetcher.fetch", return_value=(None, "500_ERROR")):
        import asyncio
        asyncio.run(coll.collect_all(db_session))
        db_session.commit()

    # Verify source was disabled
    recreated_session = sessionmaker(bind=db_session.bind)()
    updated_source = recreated_session.query(Source).filter_by(id="src-failed-1").first()
    assert updated_source.enabled is False
    assert updated_source.disabled_reason == "5 consecutive failures"
    assert updated_source.disabled_at is not None

    # Verify metric
    metric = recreated_session.query(SystemMetric).filter_by(metric_name="dead_feeds_detected").first()
    assert metric is not None
    assert metric.metric_value == 1.0
    assert metric.aggregation_type == "COUNTER"
    assert metric.source == "CollectionService"
    recreated_session.close()

def test_admin_report_generation(db_session: Session) -> None:
    """Test 5: Verify generate_daily_admin_report aggregates correct values."""
    # Seed system metric aggregates
    from src.services.metrics_service import MetricsService
    ms = MetricsService()
    ms.record_metric(db_session, "feeds_processed", 2.0)
    ms.record_metric(db_session, "articles_fetched", 10.0)
    ms.record_metric(db_session, "events_created", 1.0)
    db_session.commit()

    # Seed 1 active feed, 1 dead feed
    s1 = Source(id="s1", name="Active", domain="a.com", rss_url="http://a", source_type="RSS", source_tier=1, policy="BLOCKED", enabled=True)
    s2 = Source(id="s2", name="Dead", domain="b.com", rss_url="http://b", source_type="RSS", source_tier=1, policy="BLOCKED", enabled=False, disabled_reason="5 consecutive failures")
    db_session.add_all([s1, s2])
    db_session.commit()

    hs = HealthService()
    report = hs.generate_daily_admin_report(db_session)

    assert report["system_status"] in {"healthy", "warning", "critical"}
    assert report["feeds_processed"] == 2
    assert report["articles_fetched"] == 10
    assert report["events_created"] == 1
    assert report["dead_feeds"] == 1
    assert report["active_feeds"] == 1
    assert report["memory_usage_mb"] >= 0.0
    assert report["database_size_mb"] >= 0.0

def test_memory_collection_fallback() -> None:
    """Test 6: Memory utility falls back gracefully across libraries."""
    # Case A: psutil succeeds
    mock_psutil = MagicMock()
    mock_proc = MagicMock()
    mock_proc.memory_info.return_value = MagicMock(rss=10 * 1024 * 1024)
    mock_psutil.Process.return_value = mock_proc
    
    with patch.dict("sys.modules", {"psutil": mock_psutil}):
        mem = get_memory_usage_mb()
        assert mem == 10.0

    # Case B: psutil fails, resource succeeds
    mock_resource = MagicMock()
    mock_resource.getrusage.return_value = MagicMock(ru_maxrss=20 * 1024) # 20MB in KB
    
    with patch.dict("sys.modules", {"psutil": None, "resource": mock_resource}), \
         patch("platform.system", return_value="Linux"):
        mem = get_memory_usage_mb()
        assert mem == 20.0

    # Case C: psutil/resource fail, ctypes fails -> defaults to 0.0
    with patch.dict("sys.modules", {"psutil": None, "resource": None}), \
         patch("ctypes.windll", create=True) as mock_dll:
        mock_dll.psapi.GetProcessMemoryInfo.return_value = False
        mem = get_memory_usage_mb()
        assert mem == 0.0

def test_database_size_metric() -> None:
    """Test 7: Database size utility reports SQLite file size on disk."""
    fd, temp_db_path = tempfile.mkstemp()
    with open(temp_db_path, "wb") as f:
        # Write 2 MB of dummy bytes
        f.write(b"\0" * (2 * 1024 * 1024))
    
    with patch("src.config.settings.settings.DATABASE_URL", f"sqlite:///{temp_db_path}"):
        size = get_db_size_mb()
        assert round(size, 1) == 2.0
        
    os.close(fd)
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

def test_scheduler_heartbeat_registration() -> None:
    """Test 8: Verify heartbeat job registration in SchedulerService."""
    # Reset singleton instance
    SchedulerService._instance = None
    
    scheduler_service = SchedulerService(
        collection_service=MagicMock(),
        event_service=MagicMock(),
        digest_service=MagicMock(),
        telegram_service=MagicMock(),
        telegram_formatter=MagicMock(),
        publication_service=MagicMock()
    )
    
    # Mock scheduler start/running
    scheduler_service.scheduler = MagicMock()
    scheduler_service.scheduler.running = False
    
    scheduler_service.start()
    
    # Verify add_job was called for heartbeat
    heartbeat_job_added = False
    for call in scheduler_service.scheduler.add_job.call_args_list:
        args, kwargs = call
        if kwargs.get("id") == "system_heartbeat":
            heartbeat_job_added = True
            assert kwargs.get("trigger") == "interval"
            assert kwargs.get("minutes") == 10
            
    assert heartbeat_job_added, "System heartbeat job not added to scheduler"
