"""
Integration tests for checking database tables, constraints, relationships, and repositories.
Uses a temporary file-based SQLite database for safety.
"""

import os
import tempfile
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker, Session

from src.database.base import Base
from src.models.source import Source
from src.models.event import Event
from src.models.article import Article
from src.models.review_consensus import ReviewConsensus
from src.models.digest import Digest
from src.models.published_post import PublishedPost
from src.models.settings import Settings

# Import repositories
from src.database.repositories.source_repository import SourceRepository
from src.database.repositories.article_repository import ArticleRepository
from src.database.repositories.event_repository import EventRepository
from src.database.repositories.review_repository import ReviewConsensusRepository
from src.database.repositories.digest_repository import DigestRepository
from src.database.repositories.published_post_repository import PublishedPostRepository
from src.database.repositories.settings_repository import SettingsRepository

@pytest.fixture(name="db_session")
def fixture_db_session() -> Session:
    """Fixture to create a temporary database file on disk, initialize tables, and yield a session."""
    fd, temp_db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    
    # Configure SQLite engine with foreign key enforcement
    engine = create_engine(f"sqlite:///{temp_db_path}")
    
    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.close()

    # Create all tables and indexes
    Base.metadata.create_all(bind=engine)
    
    # Establish session
    TestingSessionLocal = sessionmaker(
        autocommit=False, 
        autoflush=False, 
        bind=engine
    )
    session = TestingSessionLocal()
    
    yield session
    
    # Teardown
    session.close()
    engine.dispose()
    try:
        os.remove(temp_db_path)
    except OSError:
        pass

def test_settings_crud_and_latest(db_session: Session) -> None:
    """Tests CRUD and get_latest functionality for Settings repository."""
    repo = SettingsRepository()
    
    # Assert initially empty
    assert len(repo.get_all(db_session)) == 0
    
    # Create first config
    config1 = Settings(
        article_retention_days=30,
        image_retention_days=60,
        log_retention_days=15,
        breaking_threshold=70,
        digest_threshold=50,
        max_articles_per_digest=10,
        cleanup_hour=4,
        keep_images=False,
        created_at=datetime(2026, 6, 15, 12, 0, 0)
    )
    repo.create(db_session, config1)
    db_session.commit()
    
    # Create second config (latest)
    config2 = Settings(
        article_retention_days=90,
        image_retention_days=180,
        log_retention_days=30,
        breaking_threshold=80,
        digest_threshold=60,
        max_articles_per_digest=12,
        cleanup_hour=2,
        keep_images=True,
        created_at=datetime(2026, 6, 15, 12, 0, 1)
    )
    repo.create(db_session, config2)
    db_session.commit()
    
    # Verify latest
    latest = repo.get_latest(db_session)
    assert latest is not None
    assert latest.article_retention_days == 90
    assert latest.cleanup_hour == 2
    assert latest.keep_images is True

def test_source_and_article_relationships(db_session: Session) -> None:
    """Verifies CRUD and relationships between Sources and Articles."""
    source_repo = SourceRepository()
    article_repo = ArticleRepository()

    # Create Source
    source = Source(
        name="Hollywood Reporter",
        domain="hollywoodreporter.com",
        rss_url="https://hollywoodreporter.com/feed",
        source_type="RSS",
        source_tier=1,
        policy="SUMMARY_ALLOWED"
    )
    source_repo.create(db_session, source)
    db_session.commit()

    # Retrieve source by domain
    retrieved_source = source_repo.get_by_domain(db_session, "hollywoodreporter.com")
    assert retrieved_source is not None
    assert retrieved_source.name == "Hollywood Reporter"

    # Create Article linked to Source
    article = Article(
        source_id=source.id,
        title="New Dune Movie Announced",
        url="https://hollywoodreporter.com/dune-announcement",
        description="Legendary announced another sequel.",
        hash="hash123dune",
        category="Movie",
        importance_score=85,
        region="GLOBAL",
        status="new"
    )
    article_repo.create(db_session, article)
    db_session.commit()

    # Verify relationships
    assert len(source.articles) == 1
    assert source.articles[0].title == "New Dune Movie Announced"
    assert article.source.name == "Hollywood Reporter"

    # Verify Article retrieval by hash and URL
    assert article_repo.get_by_hash(db_session, "hash123dune") is not None
    assert article_repo.get_by_url(db_session, "https://hollywoodreporter.com/dune-announcement") is not None

def test_event_and_review_consensus_one_to_one(db_session: Session) -> None:
    """Verifies Event and ReviewConsensus CRUD and relationships."""
    event_repo = EventRepository()
    review_repo = ReviewConsensusRepository()

    # Create Event
    event_obj = Event(
        canonical_title="Squid Game Season 2",
        event_type="Official Announcements",
        importance_score=90,
        region="KOREA",
        status="RELEASED",
        is_featured=True
    )
    event_repo.create(db_session, event_obj)
    db_session.commit()

    # Create ReviewConsensus
    consensus = ReviewConsensus(
        event_id=event_obj.id,
        title="Squid Game Season 2 - Review Consensus",
        critic_score=88,
        audience_score=85,
        consensus_summary="A stellar sequel that lives up to the hype.",
        review_count=150,
        review_source_count=10,
        sentiment="POSITIVE"
    )
    review_repo.create(db_session, consensus)
    db_session.commit()

    # Check relationships
    assert event_obj.review_consensus is not None
    assert event_obj.review_consensus.critic_score == 88
    assert consensus.event.canonical_title == "Squid Game Season 2"

    # Check query helper
    fetched_consensus = review_repo.get_by_event_id(db_session, event_obj.id)
    assert fetched_consensus is not None
    assert fetched_consensus.critic_score == 88

def test_digest_and_published_post_relationships(db_session: Session) -> None:
    """Verifies Digest and PublishedPost CRUD and relationships."""
    digest_repo = DigestRepository()
    post_repo = PublishedPostRepository()

    # Create Digest
    digest = Digest(
        digest_type="MORNING",
        content="Good morning! Here is the latest Hollywood news.",
        image_path="/data/images/morning_digest.png"
    )
    digest_repo.create(db_session, digest)
    db_session.commit()

    # Create PublishedPost
    post = PublishedPost(
        digest_id=digest.id,
        platform="TELEGRAM",
        external_id="msg_98765",
        published_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    post_repo.create(db_session, post)
    db_session.commit()

    # Check relationship
    assert len(digest.published_posts) == 1
    assert digest.published_posts[0].platform == "TELEGRAM"
    assert post.digest.digest_type == "MORNING"

    # Check query helper
    fetched_posts = post_repo.get_by_digest_id(db_session, digest.id)
    assert len(fetched_posts) == 1
    assert fetched_posts[0].external_id == "msg_98765"

def test_unique_constraints(db_session: Session) -> None:
    """Verifies unique constraint violations trigger IntegrityErrors."""
    source_repo = SourceRepository()
    event_repo = EventRepository()
    article_repo = ArticleRepository()

    # 1. Source domain unique constraint
    source1 = Source(
        name="Hollywood Reporter", domain="hollywoodreporter.com",
        source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED"
    )
    source_repo.create(db_session, source1)
    db_session.commit()

    source2 = Source(
        name="HR Clone", domain="hollywoodreporter.com",
        source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED"
    )
    with pytest.raises(IntegrityError):
        source_repo.create(db_session, source2)
        db_session.commit()
    db_session.rollback()

    # 2. Event uniqueness composite unique constraint
    event1 = Event(
        canonical_title="Pushpa 2", event_type="Release Dates",
        region="INDIA", status="RELEASED", event_pattern="RELEASE_DATE",
        season_number=0, event_year=0
    )
    event_repo.create(db_session, event1)
    db_session.commit()

    event2 = Event(
        canonical_title="Pushpa 2", event_type="Release Dates",
        region="INDIA", status="RELEASED", event_pattern="RELEASE_DATE",
        season_number=0, event_year=0
    )
    with pytest.raises(IntegrityError):
        event_repo.create(db_session, event2)
        db_session.commit()
    db_session.rollback()

    # 3. Article hash unique constraint
    article1 = Article(
        source_id=source1.id, title="Title 1", url="https://variety.com/1",
        hash="uniquehash123", category="Movie", status="new"
    )
    article_repo.create(db_session, article1)
    db_session.commit()

    article2 = Article(
        source_id=source1.id, title="Title 2", url="https://variety.com/2",
        hash="uniquehash123", category="Movie", status="new"
    )
    with pytest.raises(IntegrityError):
        article_repo.create(db_session, article2)
        db_session.commit()
    db_session.rollback()
