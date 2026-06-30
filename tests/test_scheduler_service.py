"""
Tests for SchedulerService.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.services.scheduler_service import SchedulerService
from src.feeds.collection_service import CollectionService
from src.processing.events.event_service import EventService
from src.processing.digests.digest_service import DigestService
from src.services.telegram_service import TelegramService
from src.processing.digests.telegram_formatter import TelegramFormatter

from src.services.publication_service import PublicationService

@pytest.fixture(autouse=True)
def reset_singleton():
    # Reset singleton instance between tests
    SchedulerService._instance = None

def test_scheduler_initialization() -> None:
    """Verifies that dependency injection works and scheduler starts properly."""
    coll = MagicMock(spec=CollectionService)
    evts = MagicMock(spec=EventService)
    digs = MagicMock(spec=DigestService)
    tg = MagicMock(spec=TelegramService)
    tg_f = MagicMock(spec=TelegramFormatter)
    pub_service = MagicMock(spec=PublicationService)

    service = SchedulerService(
        collection_service=coll,
        event_service=evts,
        digest_service=digs,
        telegram_service=tg,
        telegram_formatter=tg_f,
        publication_service=pub_service
    )

    assert service.collection_service is coll
    assert service.event_service is evts
    assert service.digest_service is digs
    assert service.telegram_service is tg
    assert service.telegram_formatter is tg_f
    assert service.publication_service is pub_service

def test_duplicate_scheduler_prevention() -> None:
    """Verifies that duplicate scheduler initialization returns the same instance and start checks running state."""
    service1 = SchedulerService()
    service2 = SchedulerService()
    assert service1 is service2

    # Check already running prevention
    service1.scheduler = MagicMock()
    service1.scheduler.running = True
    
    with patch.object(service1.scheduler, "add_job") as mock_add:
        service1.start()
        # Should early exit and not add jobs again
        mock_add.assert_not_called()

def test_graceful_shutdown() -> None:
    """Verifies that scheduler shutdown terminates running triggers cleanly."""
    service = SchedulerService()
    service.scheduler = MagicMock()
    service.scheduler.running = True

    service.shutdown()
    service.scheduler.shutdown.assert_called_once()

@patch("src.database.database.SessionLocal")
def test_morning_digest_job(mock_session_cls) -> None:
    """Test 1: Morning digest job workflow execution."""
    coll = MagicMock(spec=CollectionService)
    coll.collect_all = AsyncMock()
    evts = MagicMock(spec=EventService)
    digs = MagicMock(spec=DigestService)
    digs.digest_selector = MagicMock()
    digs.generate_digest = MagicMock(return_value="Dune Messiah Begins Production")
    tg = MagicMock(spec=TelegramService)
    tg.send_digest = MagicMock(return_value={"success": True})
    tg_f = MagicMock(spec=TelegramFormatter)
    pub_service = MagicMock(spec=PublicationService)

    service = SchedulerService(
        collection_service=coll,
        event_service=evts,
        digest_service=digs,
        telegram_service=tg,
        telegram_formatter=tg_f,
        publication_service=pub_service
    )

    # Mock DB query results for new articles
    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    mock_db.query.return_value.filter_by.return_value.all.return_value = []

    # Mock digest_selector events to mark published
    mock_event = MagicMock()
    mock_event.id = "e-1"
    service.digest_service.digest_selector.select_events_for_digest.return_value = [mock_event]

    service.run_morning_digest_job()

    coll.collect_all.assert_called_once()
    digs.generate_digest.assert_called_once_with(mock_db, digest_type="morning", telegram_safe=True)
    tg.send_digest.assert_called_once_with("Dune Messiah Begins Production")
    pub_service.mark_published.assert_called_once_with(mock_db, "e-1", "TELEGRAM", "DIGEST_MORNING", external_id=None, metadata={})
    mock_db.commit.assert_called()
    mock_db.close.assert_called_once()

@patch("src.database.database.SessionLocal")
def test_evening_digest_job(mock_session_cls) -> None:
    """Test 2: Evening digest job workflow execution."""
    coll = MagicMock(spec=CollectionService)
    coll.collect_all = AsyncMock()
    evts = MagicMock(spec=EventService)
    digs = MagicMock(spec=DigestService)
    digs.digest_selector = MagicMock()
    digs.generate_digest = MagicMock(return_value="Dune Messiah Begins Production")
    tg = MagicMock(spec=TelegramService)
    tg.send_digest = MagicMock(return_value={"success": True})
    tg_f = MagicMock(spec=TelegramFormatter)
    pub_service = MagicMock(spec=PublicationService)

    service = SchedulerService(
        collection_service=coll,
        event_service=evts,
        digest_service=digs,
        telegram_service=tg,
        telegram_formatter=tg_f,
        publication_service=pub_service
    )

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    mock_db.query.return_value.filter_by.return_value.all.return_value = []
    service.digest_service.digest_selector.select_events_for_digest.return_value = []

    service.run_evening_digest_job()

    coll.collect_all.assert_called_once()
    digs.generate_digest.assert_called_once_with(mock_db, digest_type="evening", telegram_safe=True)
    tg.send_digest.assert_called_once_with("Dune Messiah Begins Production")
    mock_db.close.assert_called_once()

@patch("src.database.database.SessionLocal")
def test_breaking_alert_job(mock_session_cls) -> None:
    """Test 3: Breaking alert job workflow, filtering out already published ones."""
    coll = MagicMock(spec=CollectionService)
    coll.collect_all = AsyncMock()
    evts = MagicMock(spec=EventService)
    digs = MagicMock(spec=DigestService)
    
    # Mock breaking events: one already published, one not
    evt_already_pub = MagicMock()
    evt_already_pub.id = "already_pub"
    evt_new = MagicMock()
    evt_new.id = "new_event"
    
    digs.get_breaking_events = MagicMock(return_value=[evt_already_pub, evt_new])
    
    tg = MagicMock(spec=TelegramService)
    tg.send_breaking_alert = MagicMock(return_value={"success": True})
    
    tg_f = MagicMock(spec=TelegramFormatter)
    tg_f.format_breaking_alert = MagicMock(return_value="🚨 Breaking Alert!")
    pub_service = MagicMock(spec=PublicationService)
    pub_service.is_published.side_effect = lambda session, event_id, platform, post_type: event_id == "already_pub"

    service = SchedulerService(
        collection_service=coll,
        event_service=evts,
        digest_service=digs,
        telegram_service=tg,
        telegram_formatter=tg_f,
        publication_service=pub_service
    )

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    mock_db.query.return_value.filter_by.return_value.all.return_value = []

    service.run_breaking_alert_job()

    coll.collect_all.assert_called_once()
    digs.get_breaking_events.assert_called_once_with(mock_db)
    tg_f.format_breaking_alert.assert_called_once_with(evt_new)
    tg.send_breaking_alert.assert_called_once_with("🚨 Breaking Alert!")
    pub_service.mark_published.assert_called_once_with(mock_db, "new_event", "TELEGRAM", "BREAKING_ALERT", external_id=None, metadata={})
    mock_db.commit.assert_called()
    mock_db.close.assert_called_once()

@patch("src.database.database.SessionLocal")
@patch("src.config.settings.settings")
@patch("pathlib.Path.exists")
def test_cleanup_job(mock_exists, mock_app_settings, mock_session_cls) -> None:
    """Test 4: Cleanup job fetches settings, runs DB article purge, and cleans directory files."""
    mock_exists.return_value = True
    mock_app_settings.IMAGE_DIR = MagicMock()
    mock_app_settings.LOG_DIR = MagicMock()
    
    # Mock settings values
    mock_settings_rec = MagicMock()
    mock_settings_rec.article_retention_days = 30
    mock_settings_rec.image_retention_days = 90
    mock_settings_rec.log_retention_days = 10

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db
    # Mock querying Settings
    mock_db.query.return_value.first.return_value = mock_settings_rec

    # Mock directories
    mock_image_file = MagicMock()
    mock_image_file.is_file.return_value = True
    mock_image_file.stat.return_value.st_mtime = 0  # Very old
    mock_app_settings.IMAGE_DIR.iterdir.return_value = [mock_image_file]

    mock_log_file = MagicMock()
    mock_log_file.is_file.return_value = True
    mock_log_file.stat.return_value.st_mtime = 0  # Very old
    mock_app_settings.LOG_DIR.iterdir.return_value = [mock_log_file]

    service = SchedulerService()
    service.run_cleanup_job()

    # Verify article purge query was run
    mock_db.query.return_value.filter.return_value.delete.assert_called_once()
    mock_db.commit.assert_called()

    # Verify filesystem deletions
    mock_image_file.unlink.assert_called_once()
    mock_log_file.unlink.assert_called_once()
    mock_db.close.assert_called_once()

@patch("src.database.database.SessionLocal")
def test_job_exception_handling_survival(mock_session_cls) -> None:
    """Test 5: Verify that job failure does not crash the scheduler and commits are rolled back."""
    coll = MagicMock(spec=CollectionService)
    # Raising error in collect_all
    coll.collect_all = AsyncMock(side_effect=RuntimeError("Feed system offline"))

    service = SchedulerService(
        collection_service=coll
    )

    mock_db = MagicMock()
    mock_session_cls.return_value = mock_db

    # Execution should survive and rollback, not raise exception
    try:
        service.run_morning_digest_job()
    except RuntimeError:
        pytest.fail("Scheduler job exception leaked outside!")

    mock_db.rollback.assert_called_once()
    mock_db.close.assert_called_once()
