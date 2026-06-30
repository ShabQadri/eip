"""
Tests for Publication Tracking System.
"""

from datetime import datetime, timezone
import json
import sqlite3
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from src.database.base import Base
from src.models.event import Event
from src.models.published_post import PublishedPost
from src.services.publication_service import PublicationService
from src.processing.digests.digest_selector import DigestSelector

def test_digest_already_published() -> None:
    """Verify that an event already published to morning/evening digests is excluded."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()
    selector = DigestSelector(publication_service=pub_service)

    # Seed events
    evt_pub = Event(
        id="evt-1",
        canonical_title="Dune Messiah",
        event_type="Movie",
        importance_score=90,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    evt_unpub = Event(
        id="evt-2",
        canonical_title="Wednesday Season 2",
        event_type="TV Series",
        importance_score=85,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add_all([evt_pub, evt_unpub])
    session.commit()

    # Mark evt_pub as published in a morning digest
    pub_service.mark_published(session, evt_pub.id, "TELEGRAM", "DIGEST_MORNING")
    session.commit()

    selected = selector.select_events_for_digest(session)
    assert len(selected) == 1
    assert selected[0].id == "evt-2"
    session.close()

def test_breaking_alert_already_published() -> None:
    """Verify that a breaking alert already published is detected."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()

    # Seed event
    evt = Event(
        id="evt-breaking",
        canonical_title="Dune Casting Announcement",
        event_type="Movie",
        importance_score=95,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(evt)
    session.commit()

    # Initially, it's not published
    assert not pub_service.is_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT")

    # Mark published
    pub_service.mark_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT", external_id="msg-100")
    session.commit()

    # Now it is published
    assert pub_service.is_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT")
    
    # Retrieve the post
    publications = pub_service.get_publications(session, evt.id)
    assert len(publications) == 1
    assert publications[0].external_id == "msg-100"
    assert publications[0].metadata_json == {"message_id": "msg-100"}
    assert publications[0].post_type == "BREAKING_ALERT"
    session.close()

def test_telegram_post_already_published() -> None:
    """Verify that Telegram direct post publication is tracked."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()

    evt = Event(
        id="evt-tg",
        canonical_title="Gladiator II Release Date",
        event_type="Movie",
        importance_score=88,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(evt)
    session.commit()

    pub_service.mark_published(session, evt.id, "TELEGRAM", "TELEGRAM", external_id="tg-msg-200")
    session.commit()

    assert pub_service.is_published(session, evt.id, "TELEGRAM", "TELEGRAM")
    publications = pub_service.get_publications(session, evt.id)
    assert len(publications) == 1
    assert publications[0].external_id == "tg-msg-200"
    assert publications[0].post_type == "TELEGRAM"
    session.close()

def test_multiple_publications_on_same_event() -> None:
    """Verify that multiple publications across platforms and types are tracked on a single event."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()

    evt = Event(
        id="evt-multi",
        canonical_title="Avengers Doomsday",
        event_type="Movie",
        importance_score=99,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(evt)
    session.commit()

    # Mark published in morning digest
    pub_service.mark_published(session, evt.id, "TELEGRAM", "DIGEST_MORNING")
    # Mark published in evening digest
    pub_service.mark_published(session, evt.id, "TELEGRAM", "DIGEST_EVENING")
    # Mark published on website
    pub_service.mark_published(session, evt.id, "WEBSITE", "WEBSITE", external_id="web-300")
    # Mark published on Instagram
    pub_service.mark_published(session, evt.id, "INSTAGRAM", "INSTAGRAM", external_id="ig-400")

    session.commit()

    publications = pub_service.get_publications(session, evt.id)
    assert len(publications) == 4
    
    # Assert specific records
    platforms = {p.platform for p in publications}
    post_types = {p.post_type for p in publications}
    
    assert "TELEGRAM" in platforms
    assert "WEBSITE" in platforms
    assert "INSTAGRAM" in platforms
    
    assert "DIGEST_MORNING" in post_types
    assert "DIGEST_EVENING" in post_types
    assert "WEBSITE" in post_types
    assert "INSTAGRAM" in post_types
    session.close()

def test_duplicate_prevention_flow() -> None:
    """Verify duplicate prevention logic by checking is_published before mark_published."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()

    evt = Event(
        id="evt-dup",
        canonical_title="Dune 3 Begins Filming",
        event_type="Movie",
        importance_score=92,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(evt)
    session.commit()

    # Simulating the publishing check/send workflow
    sent_count = 0
    for _ in range(3):
        if not pub_service.is_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT"):
            # Send message and mark published
            pub_service.mark_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT")
            session.commit()
            sent_count += 1

    assert sent_count == 1
    assert pub_service.is_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT")
    session.close()

def test_unique_constraint_enforcement() -> None:
    """Verify unique constraint prevents duplicate publications for same (event_id, platform, post_type)."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()

    evt = Event(
        id="evt-unique",
        canonical_title="Gladiator Sequel",
        event_type="Movie",
        importance_score=85,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(evt)
    session.commit()

    # First insert passes
    pub_service.mark_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT")
    session.commit()

    # Second insert with same event_id, platform, post_type must fail
    with pytest.raises(IntegrityError):
        pub_service.mark_published(session, evt.id, "TELEGRAM", "BREAKING_ALERT")
        session.commit()

    session.close()

def test_get_publication_helper() -> None:
    """Verify get_publication() returns correct Optional[PublishedPost]."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()

    evt = Event(
        id="evt-get",
        canonical_title="Batman Part II",
        event_type="Movie",
        importance_score=90,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(evt)
    session.commit()

    pub_service.mark_published(session, evt.id, "WEBSITE", "WEBSITE", external_id="slug-batman")
    session.commit()

    # Query existing
    pub = pub_service.get_publication(session, evt.id, "WEBSITE", "WEBSITE")
    assert pub is not None
    assert pub.external_id == "slug-batman"

    # Query non-existing
    pub_none = pub_service.get_publication(session, evt.id, "TELEGRAM", "TELEGRAM")
    assert pub_none is None

    session.close()

def test_metadata_json_default() -> None:
    """Verify metadata_json defaults to empty dictionary when not provided."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    pub_service = PublicationService()

    evt = Event(
        id="evt-meta-default",
        canonical_title="Dune Sequel Plans",
        event_type="Movie",
        importance_score=80,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session.add(evt)
    session.commit()

    post = pub_service.mark_published(session, evt.id, "WEBSITE", "WEBSITE")
    session.commit()

    assert post.metadata_json == {}
    assert isinstance(post.metadata_json, dict)

    session.close()

def test_migration_row_count_validation() -> None:
    """Verify migration row count validation and old-to-new transformation using in-memory SQLite schema copy."""
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    # 1. Create old table schema
    cursor.execute("""
        CREATE TABLE published_posts (
            id VARCHAR(36) PRIMARY KEY, 
            digest_id VARCHAR(36), 
            event_id VARCHAR(36), 
            platform VARCHAR(50) NOT NULL, 
            post_type VARCHAR(50), 
            telegram_message_id VARCHAR(100), 
            external_post_id VARCHAR(255), 
            posted_at DATETIME NOT NULL,
            created_at DATETIME,
            updated_at DATETIME
        )
    """)

    # Seed 4 old rows
    cursor.execute("INSERT INTO published_posts VALUES ('p-1', 'd-1', 'evt-1', 'TELEGRAM', 'DIGEST_MORNING', 'msg-100', NULL, '2026-06-16 12:00:00', NULL, NULL)")
    cursor.execute("INSERT INTO published_posts VALUES ('p-2', 'd-1', 'evt-2', 'WEBSITE', 'WEBSITE', NULL, 'slug-200', '2026-06-16 12:05:00', NULL, NULL)")
    cursor.execute("INSERT INTO published_posts VALUES ('p-3', 'd-1', 'evt-3', 'INSTAGRAM', 'INSTAGRAM', NULL, 'post-300', '2026-06-16 12:10:00', NULL, NULL)")
    cursor.execute("INSERT INTO published_posts VALUES ('p-4', 'd-1', 'evt-1', 'TELEGRAM', 'DIGEST_MORNING', 'msg-100-dup', NULL, '2026-06-16 12:15:00', NULL, NULL)")
    conn.commit()

    # 2. Run SQL transformation logic matching migrate_published_posts.py
    cursor.execute("PRAGMA table_info(published_posts)")
    columns = [col[1] for col in cursor.fetchall()]

    assert "telegram_message_id" in columns
    assert "external_post_id" in columns

    cursor.execute("SELECT id, digest_id, event_id, platform, post_type, telegram_message_id, external_post_id, posted_at, created_at, updated_at FROM published_posts")
    old_rows = cursor.fetchall()
    old_row_count = len(old_rows)
    assert old_row_count == 4

    # Create new table schema
    cursor.execute("""
        CREATE TABLE published_posts_new (
            id VARCHAR(36) NOT NULL, 
            digest_id VARCHAR(36), 
            event_id VARCHAR(36), 
            post_type VARCHAR(50), 
            platform VARCHAR(50) NOT NULL, 
            external_id VARCHAR(255), 
            metadata_json JSON NOT NULL, 
            published_at DATETIME NOT NULL, 
            created_at DATETIME, 
            updated_at DATETIME, 
            PRIMARY KEY (id),
            CONSTRAINT uq_publication_tracking UNIQUE (event_id, platform, post_type)
        )
    """)

    duplicate_rows = 0
    inserted_keys = set()
    for row in old_rows:
        post_id, digest_id, event_id, platform, post_type, tg_msg_id, ext_post_id, pub_at, created_at, updated_at = row
        unique_key = (event_id, platform, post_type)
        if unique_key in inserted_keys:
            duplicate_rows += 1
            continue
        inserted_keys.add(unique_key)
        
        ext_id = tg_msg_id or ext_post_id or None
        meta = {}
        if platform == "TELEGRAM" and ext_id:
            meta["message_id"] = ext_id
        elif platform == "WEBSITE":
            meta["slug"] = ext_id or ""
        elif platform == "INSTAGRAM":
            meta["post_id"] = ext_id or ""
            meta["media_id"] = ""

        cursor.execute("""
            INSERT INTO published_posts_new (id, digest_id, event_id, platform, post_type, external_id, metadata_json, published_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (post_id, digest_id, event_id, platform, post_type, ext_id, json.dumps(meta), pub_at, created_at, updated_at))

    cursor.execute("SELECT COUNT(*) FROM published_posts_new")
    new_row_count = cursor.fetchone()[0]

    assert old_row_count == 4
    assert new_row_count == 3
    assert duplicate_rows == 1
    assert (old_row_count - new_row_count - duplicate_rows) == 0

    # Verify data mapping
    cursor.execute("SELECT id, external_id, metadata_json FROM published_posts_new WHERE id='p-1'")
    r1 = cursor.fetchone()
    assert r1[1] == "msg-100"
    assert json.loads(r1[2]) == {"message_id": "msg-100"}

    cursor.execute("SELECT id, external_id, metadata_json FROM published_posts_new WHERE id='p-2'")
    r2 = cursor.fetchone()
    assert r2[1] == "slug-200"
    assert json.loads(r2[2]) == {"slug": "slug-200"}

    cursor.execute("SELECT id, external_id, metadata_json FROM published_posts_new WHERE id='p-3'")
    r3 = cursor.fetchone()
    assert r3[1] == "post-300"
    assert json.loads(r3[2]) == {"post_id": "post-300", "media_id": ""}

    conn.close()

def test_concurrent_duplicate_insertion_prevention() -> None:
    """Verify that attempts to write concurrent duplicate publications fail at the database level."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    
    session1 = Session()
    session2 = Session()

    pub_service = PublicationService()

    # Seed event
    evt = Event(
        id="evt-concur",
        canonical_title="Dune 3 casting info",
        event_type="Movie",
        importance_score=80,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None)
    )
    session1.add(evt)
    session1.commit()

    # Session 1 marks published
    pub_service.mark_published(session1, "evt-concur", "TELEGRAM", "BREAKING_ALERT")
    session1.commit()

    # Session 2 attempts to mark published for same event, platform, post_type
    with pytest.raises(IntegrityError):
        pub_service.mark_published(session2, "evt-concur", "TELEGRAM", "BREAKING_ALERT")
        session2.commit()

    session1.close()
    session2.close()
