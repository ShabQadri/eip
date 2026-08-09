"""
Tests for DigestSelector.
"""

from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import Base
from src.models.event import Event
from src.models.settings import Settings
from src.models.published_post import PublishedPost
from src.processing.digests.digest_selector import DigestSelector

def test_digest_selector_initialization() -> None:
    """Verifies DigestSelector default values."""
    selector = DigestSelector()
    assert selector.digest_threshold == 60
    assert selector.max_articles == 12

def test_digest_selector_scenarios() -> None:
    """Verifies select_events_for_digest scenarios."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed settings
    settings = Settings(
        digest_threshold=60,
        max_articles_per_digest=12
    )
    session.add(settings)
    session.commit()

    selector = DigestSelector()
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Test Case 1: 15 eligible events, limit = None -> Expected: 12 returned
    events_15 = [
        Event(
            canonical_title=f"Eligible {i}",
            event_type="Movie",
            importance_score=70,
            last_article_at=now - timedelta(minutes=i))
        for i in range(15)
    ]
    session.add_all(events_15)
    session.commit()

    selected = selector.select_events_for_digest(session)
    assert len(selected) == 12

    # Cleanup database for next tests
    session.query(PublishedPost).delete()
    session.query(Event).delete()
    session.commit()

    # 2. Test Case 2: 5 eligible events -> Expected: 5 returned
    events_5 = [
        Event(
            canonical_title=f"Eligible {i}",
            event_type="Movie",
            importance_score=70,
            last_article_at=now - timedelta(minutes=i))
        for i in range(5)
    ]
    session.add_all(events_5)
    session.commit()

    selected = selector.select_events_for_digest(session)
    assert len(selected) == 5

    # Cleanup
    session.query(PublishedPost).delete()
    session.query(Event).delete()
    session.commit()

    # 3. Test Case 3: importance below threshold -> Expected: excluded
    low_imp = Event(
        canonical_title="Low Importance",
        event_type="Movie",
        importance_score=50, # Below 60
        last_article_at=now)
    high_imp = Event(
        canonical_title="High Importance",
        event_type="Movie",
        importance_score=75,
        last_article_at=now)
    session.add_all([low_imp, high_imp])
    session.commit()

    selected = selector.select_events_for_digest(session)
    assert len(selected) == 1
    assert selected[0].canonical_title == "High Importance"

    # Cleanup
    session.query(PublishedPost).delete()
    session.query(Event).delete()
    session.commit()

    # 4. Test Case 4: already published event -> Expected: excluded
    pub_event = Event(
        id="pub-evt-1",
        canonical_title="Published Event",
        event_type="Movie",
        importance_score=80,
        last_article_at=now
    )
    unpub_event = Event(
        id="unpub-evt-1",
        canonical_title="Unpublished Event",
        event_type="Movie",
        importance_score=80,
        last_article_at=now)
    session.add_all([pub_event, unpub_event])
    session.commit()

    from src.services.publication_service import PublicationService
    pub_service = PublicationService()
    pub_service.mark_published(session, pub_event.id, "TELEGRAM", "DIGEST_MORNING")
    session.commit()

    selected = selector.select_events_for_digest(session)
    assert len(selected) == 1
    assert selected[0].canonical_title == "Unpublished Event"
    assert selector.is_event_published(session, pub_event.id) is True
    assert selector.is_event_published(session, unpub_event.id) is False

    # Cleanup
    session.query(PublishedPost).delete()
    session.query(Event).delete()
    session.commit()

    # 5. Test Case 5: same importance: newer event first -> Expected: sorted by last_article_at DESC
    old_time = now - timedelta(hours=2)
    new_time = now - timedelta(hours=1)
    
    old_event = Event(
        canonical_title="Old Event",
        event_type="Movie",
        importance_score=80,
        last_article_at=old_time)
    new_event = Event(
        canonical_title="New Event",
        event_type="Movie",
        importance_score=80,
        last_article_at=new_time)
    session.add_all([old_event, new_event])
    session.commit()

    selected = selector.select_events_for_digest(session)
    assert len(selected) == 2
    assert selected[0].canonical_title == "New Event"
    assert selected[1].canonical_title == "Old Event"

    session.close()
