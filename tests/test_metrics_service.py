"""
Unit and integration tests for MetricsService and Step 7.1.
"""

import os
import tempfile
import time
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
import pytest
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.orm import sessionmaker, Session

from src.database.base import Base
from src.models.settings import Settings
from src.models.system_metric import SystemMetric
from src.models.article import Article
from src.models.event import Event
from src.services.metrics_service import MetricsService
from src.services.scheduler_service import SchedulerService
from src.services.telegram_service import TelegramService
from src.processing.events.event_service import EventService
from src.feeds.collection_service import CollectionService, CollectionResult
from src.processing.digests.digest_service import DigestService

SAMPLE_RSS_XML_METRICS = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
 <title>Variety News</title>
 <link>https://variety.com</link>
 <description>Entertainment News</description>
 <item>
  <title>Official Trailer for Marvel Avengers Sequel Released</title>
  <link>https://variety.com/avengers-trailer</link>
  <description>The official trailer is now playing in theaters.</description>
  <pubDate>Mon, 15 Jun 2026 12:00:00 GMT</pubDate>
 </item>
</channel>
</rss>
"""

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
    settings = Settings(
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
    session.add(settings)
    session.commit()
    
    yield session
    
    session.close()
    engine.dispose()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

def test_metric_insertion(db_session: Session) -> None:
    """Test 1: Metric insertion preserves all columns and defaults."""
    ms = MetricsService()
    metric = ms.record_metric(
        session=db_session,
        metric_name="feeds_processed",
        metric_value=5,
        aggregation_type="COUNTER",
        source="CollectionService",
        metadata={"feed_url": "https://example.com/rss"}
    )
    db_session.commit()

    assert metric.id is not None
    assert metric.metric_name == "feeds_processed"
    assert metric.metric_value == 5.0
    assert metric.aggregation_type == "COUNTER"
    assert metric.source == "CollectionService"
    assert metric.metadata_json == {"feed_url": "https://example.com/rss"}
    assert metric.created_at is not None
    assert metric.created_at.tzinfo is not None

def test_increment_helper(db_session: Session) -> None:
    """Test 2: Increment helper works and sets correct defaults."""
    ms = MetricsService()
    
    # 1. First increment
    ms.increment(db_session, "telegram_failures", amount=1, source="TelegramService")
    # 2. Second increment with default amount=1
    ms.increment(db_session, "telegram_failures", source="TelegramService")
    db_session.commit()

    records = db_session.query(SystemMetric).filter_by(metric_name="telegram_failures").all()
    assert len(records) == 2
    assert records[0].metric_value == 1.0
    assert records[0].aggregation_type == "COUNTER"
    assert records[0].source == "TelegramService"
    assert records[1].metric_value == 1.0

def test_date_filtering(db_session: Session) -> None:
    """Test 3: Date filtering works correctly in get_metric."""
    ms = MetricsService()
    now = datetime.now(timezone.utc)
    
    # Insert metrics with manually set created_at
    m1 = SystemMetric(
        metric_name="feeds_processed",
        metric_value=1.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now - timedelta(hours=5)
    )
    m2 = SystemMetric(
        metric_name="feeds_processed",
        metric_value=2.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now - timedelta(hours=2)
    )
    m3 = SystemMetric(
        metric_name="feeds_processed",
        metric_value=3.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now + timedelta(hours=2)
    )
    db_session.add_all([m1, m2, m3])
    db_session.commit()

    # Query with start/end bounds
    start = now - timedelta(hours=4)
    end = now + timedelta(hours=1)
    
    results = ms.get_metric(db_session, "feeds_processed", start_date=start, end_date=end)
    assert len(results) == 1
    assert results[0].id == m2.id

def test_summary_generation(db_session: Session) -> None:
    """Test 4: Summary generation aggregates only recent data."""
    ms = MetricsService()
    now = datetime.now(timezone.utc)
    
    # Older than 24h (cutoff)
    m_old = SystemMetric(
        metric_name="feeds_processed",
        metric_value=10.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now - timedelta(hours=25)
    )
    # Recent metrics
    m_new1 = SystemMetric(
        metric_name="feeds_processed",
        metric_value=2.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now - timedelta(hours=5)
    )
    m_new2 = SystemMetric(
        metric_name="feeds_processed",
        metric_value=3.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now - timedelta(hours=1)
    )
    db_session.add_all([m_old, m_new1, m_new2])
    db_session.commit()

    summary = ms.daily_metrics_summary(db_session)
    assert summary["feeds_processed"] == 5  # 2 + 3

def test_metadata_persistence(db_session: Session) -> None:
    """Test 5: Arbitrary dictionary persists and can be queried."""
    ms = MetricsService()
    meta = {"job_id": "job_123", "nested": {"key": "value"}}
    ms.record_metric(db_session, "scheduler_failures", 1, metadata=meta)
    db_session.commit()

    metric = db_session.query(SystemMetric).filter_by(metric_name="scheduler_failures").first()
    assert metric.metadata_json == meta
    assert metric.metadata_json["nested"]["key"] == "value"

def test_invalid_metric_handling(db_session: Session) -> None:
    """Test 6: Invalid metric names or aggregation types raise ValueError."""
    ms = MetricsService()
    with pytest.raises(ValueError, match="Invalid metric name"):
        ms.record_metric(db_session, "invalid_metric_name_123", 1.0)
        
    with pytest.raises(ValueError, match="Invalid metric name"):
        ms.increment(db_session, "invalid_metric_name_123")

    with pytest.raises(ValueError, match="Invalid metric name"):
        ms.get_metric(db_session, "invalid_metric_name_123")

    with pytest.raises(ValueError, match="Invalid aggregation type"):
        ms.record_metric(db_session, "feeds_processed", 1.0, aggregation_type="INVALID")

def test_aggregation_correctness(db_session: Session) -> None:
    """Test 7: Summary aggregation implements SUM, AVG, MAX, and LATEST rules correctly."""
    ms = MetricsService()
    now = datetime.now(timezone.utc)
    
    # 1. COUNTER: SUM
    ms.record_metric(db_session, "events_created", 2, aggregation_type="COUNTER")
    ms.record_metric(db_session, "events_created", 3, aggregation_type="COUNTER")
    
    # 2. AVERAGE: AVG
    ms.record_metric(db_session, "average_digest_size", 4, aggregation_type="AVERAGE")
    ms.record_metric(db_session, "average_digest_size", 6, aggregation_type="AVERAGE")

    # 3. GAUGE: LATEST VALUE
    ms.record_metric(
        db_session, 
        "feeds_succeeded", 
        10.0, 
        aggregation_type="GAUGE", 
        created_at=now - timedelta(minutes=10)
    )
    ms.record_metric(
        db_session, 
        "feeds_succeeded", 
        20.0, 
        aggregation_type="GAUGE", 
        created_at=now - timedelta(minutes=5)
    )

    # 4. TIMER: AVG & MAX
    ms.record_metric(db_session, "processing_time_ms", 100.0, aggregation_type="TIMER")
    ms.record_metric(db_session, "processing_time_ms", 300.0, aggregation_type="TIMER")
    
    db_session.commit()

    summary = ms.daily_metrics_summary(db_session)
    assert summary["events_created"] == 5
    assert summary["average_digest_size"] == 5.0
    assert summary["feeds_succeeded"] == 20.0
    assert summary["processing_time_ms_avg"] == 200.0
    assert summary["processing_time_ms_max"] == 300.0

@pytest.mark.asyncio
@patch("src.database.database.SessionLocal")
async def test_service_integration(mock_session_local, db_session: Session) -> None:
    """Test 8: Subsystem service workflows record their respective metrics."""
    mock_session_local.return_value = db_session
    ms = MetricsService()
    
    # --- 1. CollectionService Ingestion stats ---
    from src.models.source import Source
    source = Source(
        id="src-1",
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

    coll = CollectionService()
    
    with patch("src.feeds.rss_fetcher.RSSFetcher.fetch") as mock_fetch:
        mock_fetch.return_value = (SAMPLE_RSS_XML_METRICS, "200_OK")
        await coll.collect_all(db_session)
        db_session.commit()
        
    assert len(ms.get_metric(db_session, "feeds_processed")) == 1
    assert len(ms.get_metric(db_session, "articles_fetched")) == 1
    
    # --- 2. EventService creation/merging ---
    art1 = Article(
        title="Spider-Man Brand New Day", 
        url="http://var.com/sp1", 
        source_id="src-1", 
        hash="h1", 
        importance_score=90, 
        created_at=datetime.now(timezone.utc)
    )
    art2 = Article(
        title="Spider-Man Brand New Day Begins", 
        url="http://var.com/sp2", 
        source_id="src-1", 
        hash="h2", 
        importance_score=85, 
        created_at=datetime.now(timezone.utc)
    )
    db_session.add_all([art1, art2])
    db_session.commit()
    
    es = EventService()
    evt1 = es.process_article(db_session, art1)
    db_session.commit()
    
    evt2 = es.process_article(db_session, art2)
    db_session.commit()

    created_metrics = ms.get_metric(db_session, "events_created")
    merged_metrics = ms.get_metric(db_session, "events_merged")
    assert len(created_metrics) == 1
    assert len(merged_metrics) == 1
    
    # --- 3. DigestService size ---
    from src.processing.digests.breaking_detector import BreakingDetector
    from src.processing.digests.digest_selector import DigestSelector
    from src.processing.digests.digest_formatter import DigestFormatter
    from src.processing.digests.telegram_formatter import TelegramFormatter
    
    ds = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(),
        telegram_formatter=TelegramFormatter()
    )
    with patch.object(ds.digest_selector, "select_events_for_digest", return_value=[evt1]):
        ds.generate_digest(db_session, "morning")
        db_session.commit()
        
    avg_size_metrics = ms.get_metric(db_session, "average_digest_size")
    assert len(avg_size_metrics) == 1
    assert avg_size_metrics[0].metric_value == 1.0

    # --- 4. TelegramService failures ---
    tgs = TelegramService(bot_token="fake", channel_id="fake")
    with patch("aiohttp.ClientSession.post", side_effect=Exception("Connection Error")):
        tgs.send_message("Testing metrics failures")
        
    tg_failures = ms.get_metric(db_session, "telegram_failures")
    assert len(tg_failures) == 1

def test_timezone_aware_timestamps(db_session: Session) -> None:
    """Test 9: Verify metric timestamps are stored with timezone-aware datetime."""
    ms = MetricsService()
    metric = ms.record_metric(db_session, "feeds_processed", 1)
    db_session.commit()
    
    queried = db_session.query(SystemMetric).filter_by(id=metric.id).first()
    assert queried.created_at.tzinfo is not None

def test_aggregation_type_rules(db_session: Session) -> None:
    """Test 10: Verify aggregation rules apply correctly to GAUGE, TIMER, COUNTER, AVERAGE."""
    ms = MetricsService()
    
    # GAUGE
    ms.record_metric(db_session, "feeds_succeeded", 5.0, aggregation_type="GAUGE")
    ms.record_metric(db_session, "feeds_succeeded", 15.0, aggregation_type="GAUGE")
    
    # TIMER
    ms.record_metric(db_session, "processing_time_ms", 10.0, aggregation_type="TIMER")
    ms.record_metric(db_session, "processing_time_ms", 20.0, aggregation_type="TIMER")
    
    # COUNTER
    ms.record_metric(db_session, "feeds_processed", 2.0, aggregation_type="COUNTER")
    ms.record_metric(db_session, "feeds_processed", 3.0, aggregation_type="COUNTER")
    
    # AVERAGE
    ms.record_metric(db_session, "average_digest_size", 4.0, aggregation_type="AVERAGE")
    ms.record_metric(db_session, "average_digest_size", 6.0, aggregation_type="AVERAGE")
    
    db_session.commit()
    
    summary = ms.daily_metrics_summary(db_session)
    assert summary["feeds_succeeded"] == 15.0  # LATEST
    assert summary["processing_time_ms_avg"] == 15.0  # AVG
    assert summary["processing_time_ms_max"] == 20.0  # MAX
    assert summary["feeds_processed"] == 5  # SUM
    assert summary["average_digest_size"] == 5.0  # AVG

def test_source_filtering(db_session: Session) -> None:
    """Test 11: Verify querying metrics supports source-level filtering."""
    ms = MetricsService()
    ms.record_metric(db_session, "feeds_processed", 1, source="SourceA")
    ms.record_metric(db_session, "feeds_processed", 2, source="SourceB")
    db_session.commit()
    
    res_a = ms.get_metric(db_session, "feeds_processed", source="SourceA")
    assert len(res_a) == 1
    assert res_a[0].metric_value == 1.0

    res_b = ms.get_metric(db_session, "feeds_processed", source="SourceB")
    assert len(res_b) == 1
    assert res_b[0].metric_value == 2.0

@patch("src.database.database.SessionLocal")
def test_metric_retention_cleanup(mock_session_local, db_session: Session) -> None:
    """Test 12: Scheduler cleanup job removes metrics older than retention window."""
    mock_session_local.return_value = db_session
    
    # Clear settings to avoid duplicates
    db_session.query(Settings).delete()
    
    settings = Settings(
        article_retention_days=10,
        image_retention_days=10,
        log_retention_days=10,
        breaking_threshold=80,
        digest_threshold=60,
        max_articles_per_digest=12,
        cleanup_hour=2,
        keep_images=True,
        metric_retention_days=2  # Retention of 2 days
    )
    db_session.add(settings)
    db_session.commit()
    
    # Add metrics
    now = datetime.now(timezone.utc)
    m_old = SystemMetric(
        metric_name="feeds_processed",
        metric_value=5.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now - timedelta(days=3) # Older than 2 days
    )
    m_new = SystemMetric(
        metric_name="feeds_processed",
        metric_value=10.0,
        aggregation_type="COUNTER",
        source="CollectionService",
        created_at=now - timedelta(days=1) # Inside retention window
    )
    db_session.add_all([m_old, m_new])
    db_session.commit()
    
    m_new_id = m_new.id
    
    scheduler = SchedulerService(
        collection_service=MagicMock(),
        event_service=MagicMock(),
        digest_service=MagicMock(),
        telegram_service=MagicMock(),
        telegram_formatter=MagicMock(),
        publication_service=MagicMock()
    )
    scheduler.run_cleanup_job()
    
    # Recreate session from the db engine to prevent DetachedInstanceError on db_session
    new_session = sessionmaker(bind=db_session.bind)()
    retained = new_session.query(SystemMetric).all()
    assert len(retained) == 1
    assert retained[0].id == m_new_id
    new_session.close()

def test_composite_indexes_exist(db_session: Session) -> None:
    """Test 13: Verify system_metrics table contains the proper indexes."""
    inspector = inspect(db_session.bind)
    indexes = inspector.get_indexes("system_metrics")
    
    metric_name_created_at_exists = False
    source_created_at_exists = False
    
    for idx in indexes:
        cols = idx.get("column_names", [])
        if cols == ["metric_name", "created_at"]:
            metric_name_created_at_exists = True
        elif cols == ["source", "created_at"]:
            source_created_at_exists = True
            
    assert metric_name_created_at_exists, "Composite index (metric_name, created_at) is missing"
    assert source_created_at_exists, "Composite index (source, created_at) is missing"

def test_timer_metrics_avg_and_max(db_session: Session) -> None:
    """Test 14: Verify processing_time_ms maps to avg and max summary fields."""
    ms = MetricsService()
    ms.record_metric(db_session, "processing_time_ms", 150.0, aggregation_type="TIMER")
    ms.record_metric(db_session, "processing_time_ms", 250.0, aggregation_type="TIMER")
    db_session.commit()
    
    summary = ms.daily_metrics_summary(db_session)
    assert summary["processing_time_ms_avg"] == 200.0
    assert summary["processing_time_ms_max"] == 250.0

def test_gauge_returns_latest_value(db_session: Session) -> None:
    """Test 15: Verify GAUGE metrics return only the latest value by timestamp."""
    ms = MetricsService()
    now = datetime.now(timezone.utc)
    
    # Record a gauge metric at different times
    ms.record_metric(
        db_session,
        "feeds_succeeded",
        1.0,
        aggregation_type="GAUGE",
        created_at=now - timedelta(hours=3)
    )
    ms.record_metric(
        db_session,
        "feeds_succeeded",
        5.0,
        aggregation_type="GAUGE",
        created_at=now - timedelta(hours=1)
    )
    ms.record_metric(
        db_session,
        "feeds_succeeded",
        3.0,
        aggregation_type="GAUGE",
        created_at=now - timedelta(hours=2)
    )
    db_session.commit()
    
    summary = ms.daily_metrics_summary(db_session)
    # The latest one should be the one at 1 hour ago with value 5.0
    assert summary["feeds_succeeded"] == 5.0
