"""
Integration tests for CollectionService, circuit breaker, caching, and dry-run execution.
"""

import os
import tempfile
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session

from src.database.base import Base
from src.models.source import Source
from src.models.settings import Settings
from src.models.article import Article
from src.database.repositories.source_repository import SourceRepository
from src.database.repositories.settings_repository import SettingsRepository
from src.database.repositories.article_repository import ArticleRepository
from src.feeds.collection_service import CollectionService, CollectionResult

# Sample raw XML content for testing
SAMPLE_RSS_XML = """<?xml version="1.0" encoding="UTF-8" ?>
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
 <item>
  <title>Actor spotted dating at airport</title>
  <link>https://variety.com/gossip-airport</link>
  <description>Paparazzi caught them kissing on vacation.</description>
  <pubDate>Mon, 15 Jun 2026 12:05:00 GMT</pubDate>
 </item>
 <item>
  <title>Gallery of new styling trends</title>
  <link>https://variety.com/instagram-outfits</link>
  <description>Social media reacts to photo uploaded on their Instagram yesterday.</description>
  <pubDate>Mon, 15 Jun 2026 12:10:00 GMT</pubDate>
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
    
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine
    )
    session = TestingSessionLocal()
    
    # Seed default Settings row
    settings_repo = SettingsRepository()
    default_config = Settings(
        article_retention_days=90,
        image_retention_days=180,
        log_retention_days=30,
        breaking_threshold=80,
        digest_threshold=60,  # Default threshold
        max_articles_per_digest=12,
        cleanup_hour=2,
        keep_images=True
    )
    settings_repo.create(session, default_config)
    session.commit()
    
    yield session
    
    # Teardown
    session.close()
    engine.dispose()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

@pytest.mark.asyncio
@patch("src.feeds.rss_fetcher.RSSFetcher.fetch")
async def test_feed_collection_sweep(mock_fetch, db_session: Session) -> None:
    """Tests that the full collection sweep parses, filters, and stores articles correctly."""
    # Seed Source in database
    source_repo = SourceRepository()
    source = Source(
        name="Variety",
        domain="variety.com",
        rss_url="https://variety.com/feed/",
        source_type="RSS",
        source_tier=1,
        policy="SUMMARY_ALLOWED",
        enabled=True
    )
    source_repo.create(db_session, source)
    db_session.commit()

    # Mock fetch to return sample XML
    mock_fetch.return_value = (SAMPLE_RSS_XML, "200_OK")

    # Execute service sweep
    service = CollectionService()
    result = await service.collect_all(db_session, dry_run=False)

    # Verification of statistics
    # 1 source processed
    assert result.feeds_processed == 1
    assert result.feeds_succeeded == 1
    
    # Articles count assertions
    # Input has 3 items:
    # - "Avengers Sequel Trailer" (high-value: stored)
    # - "Actor spotted dating at airport" (contains spotted, airport, dating: pre-filtered)
    # - "Top 10 outfits on Instagram" (low-value listicle: rejected)
    assert result.articles_fetched == 3
    assert result.articles_pre_filtered == 1  # Pre-filtered gossip
    assert result.articles_rejected == 1      # Low value listicle
    assert result.articles_stored == 1        # Only the trailer is stored!
    assert result.rejected_gossip == 0        # Gossip was pre-filtered before this count
    assert result.rejected_low_value == 1     # Outfit listicle

    # Verify Article exists in database
    articles = db_session.query(Article).all()
    assert len(articles) == 1
    assert articles[0].title == "Official Trailer for Marvel Avengers Sequel Released"
    assert articles[0].category == "Movie"
    assert articles[0].importance_score == 95

    # Verify Source health fields updated
    updated_source = source_repo.get_by_id(db_session, source.id)
    assert updated_source.last_successful_fetch is not None
    assert updated_source.consecutive_failures == 0

@pytest.mark.asyncio
@patch("src.feeds.rss_fetcher.RSSFetcher.fetch")
async def test_feed_collection_duplicate_prevention(mock_fetch, db_session: Session) -> None:
    """Verifies that duplicate articles are suppressed using unique hashes."""
    source_repo = SourceRepository()
    source = Source(
        name="Variety", domain="variety.com", rss_url="https://variety.com/feed/",
        source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED", enabled=True
    )
    source_repo.create(db_session, source)
    db_session.commit()

    mock_fetch.return_value = (SAMPLE_RSS_XML, "200_OK")
    service = CollectionService()

    # First run stores 1 article
    result1 = await service.collect_all(db_session, dry_run=False)
    assert result1.articles_stored == 1

    # Second run rejects it as a duplicate
    result2 = await service.collect_all(db_session, dry_run=False)
    assert result2.articles_stored == 0
    assert result2.rejected_duplicates == 1

@pytest.mark.asyncio
@patch("src.feeds.rss_fetcher.RSSFetcher.fetch")
async def test_feed_collection_dry_run(mock_fetch, db_session: Session) -> None:
    """Verifies dry-run parses and matches statistics but does not save data to SQLite."""
    source_repo = SourceRepository()
    source = Source(
        name="Variety", domain="variety.com", rss_url="https://variety.com/feed/",
        source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED", enabled=True
    )
    source_repo.create(db_session, source)
    db_session.commit()

    mock_fetch.return_value = (SAMPLE_RSS_XML, "200_OK")
    service = CollectionService()

    result = await service.collect_all(db_session, dry_run=True)
    # Dry run reports store counts in statistics
    assert result.articles_stored == 1

    # Verify database remains empty of articles
    articles = db_session.query(Article).all()
    assert len(articles) == 0

@pytest.mark.asyncio
@patch("src.feeds.rss_fetcher.RSSFetcher.fetch")
async def test_circuit_breaker_trigger(mock_fetch, db_session: Session) -> None:
    """Verifies that the circuit breaker trips after 3 failures and skips fetches."""
    source_repo = SourceRepository()
    source = Source(
        name="Variety", domain="variety.com", rss_url="https://variety.com/feed/",
        source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED", enabled=True
    )
    source_repo.create(db_session, source)
    db_session.commit()

    # Configure fetcher to fail
    mock_fetch.return_value = (None, "HTTP_500")
    service = CollectionService()

    # Run 3 failures
    for i in range(3):
        res = await service.collect_all(db_session, dry_run=False)
        assert res.feeds_failed == 1

    # Verify health record in database
    db_session.refresh(source)
    assert source.consecutive_failures == 3
    assert source.last_failed_fetch is not None

    # Reset mock to return a success code (will not be invoked anyway due to CB)
    mock_fetch.reset_mock()
    mock_fetch.return_value = (SAMPLE_RSS_XML, "200_OK")

    # Run 4th sweep
    res4 = await service.collect_all(db_session, dry_run=False)
    # It should skip fetching, registering as a failed/skipped feed
    assert res4.articles_skipped_by_cache == 1
    assert mock_fetch.call_count == 0  # Fetch was never called!
