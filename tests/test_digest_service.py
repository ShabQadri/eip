"""
Tests for DigestService.
"""

from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import Base
from src.models.event import Event
from src.models.settings import Settings
from src.processing.digests.digest_service import DigestService
from src.processing.digests.breaking_detector import BreakingDetector
from src.processing.digests.digest_selector import DigestSelector
from src.processing.digests.digest_formatter import DigestFormatter
from src.processing.digests.telegram_formatter import TelegramFormatter

def test_digest_service_initialization() -> None:
    """Verifies DigestService initializes correctly with its dependencies."""
    detector = BreakingDetector()
    selector = DigestSelector()
    formatter = DigestFormatter()
    tg_formatter = TelegramFormatter()

    service = DigestService(
        breaking_detector=detector,
        digest_selector=selector,
        digest_formatter=formatter,
        telegram_formatter=tg_formatter
    )

    assert service.breaking_detector is detector
    assert service.digest_selector is selector
    assert service.digest_formatter is formatter
    assert service.telegram_formatter is tg_formatter


def test_generate_digest_zero_events() -> None:
    """Verifies generate_digest handles 0 events by returning empty digest message."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    detector = BreakingDetector()
    selector = DigestSelector()
    # Override date for consistency
    formatter = DigestFormatter(current_date_override="2026-06-16")
    tg_formatter = TelegramFormatter()

    service = DigestService(
        breaking_detector=detector,
        digest_selector=selector,
        digest_formatter=formatter,
        telegram_formatter=tg_formatter
    )

    result = service.generate_digest(session)
    expected = (
        "🎬 Entertainment Intelligence Digest\n"
        "🗓 2026-06-16\n"
        "\n"
        "No major entertainment developments at this time."
    )
    assert result == expected
    session.close()


def test_generate_digest_three_events() -> None:
    """Verifies generate_digest formats 3 events properly."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Seed 3 events (published=False, importance=80)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for i in range(1, 4):
        evt = Event(
            id=f"e-{i}",
            canonical_title=f"Movie {i}",
            display_title=f"Movie {i} Begins Production",
            event_type="Movie",
            event_pattern="PRODUCTION_START",
            importance_score=80,
            source_count=3,
            last_article_at=now - timedelta(seconds=i),
            published=False
        )
        session.add(evt)
    session.commit()

    detector = BreakingDetector()
    selector = DigestSelector()
    formatter = DigestFormatter(current_date_override="2026-06-16")
    tg_formatter = TelegramFormatter()

    service = DigestService(
        breaking_detector=detector,
        digest_selector=selector,
        digest_formatter=formatter,
        telegram_formatter=tg_formatter
    )

    result = service.generate_digest(session)
    assert "1. Movie 1 Begins Production" in result
    assert "2. Movie 2 Begins Production" in result
    assert "3. Movie 3 Begins Production" in result
    assert "• Importance: 80" in result
    assert "• Sources: 3" in result
    assert "• Pattern: PRODUCTION_START" in result
    session.close()


def test_generate_digest_telegram_safe_true_and_false() -> None:
    """Verifies telegram_safe=True/False runs through escaping or raw formatting."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    evt = Event(
        canonical_title="Spider-Man",
        display_title="Spider-Man: Brand New Day!",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=85,
        source_count=2,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None),
        published=False
    )
    session.add(evt)
    session.commit()

    detector = BreakingDetector()
    selector = DigestSelector()
    formatter = DigestFormatter(current_date_override="2026-06-16")
    tg_formatter = TelegramFormatter()

    service = DigestService(
        breaking_detector=detector,
        digest_selector=selector,
        digest_formatter=formatter,
        telegram_formatter=tg_formatter
    )

    # telegram_safe=False
    raw_result = service.generate_digest(session, telegram_safe=False)
    assert "Spider-Man: Brand New Day!" in raw_result

    # telegram_safe=True
    escaped_result = service.generate_digest(session, telegram_safe=True)
    # Check that '-' and '!' are escaped
    assert r"Spider\-Man: Brand New Day\!" in escaped_result
    session.close()


def test_get_breaking_events_zero() -> None:
    """Verifies get_breaking_events returns empty list when no events are breaking."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # Event below threshold
    evt = Event(
        canonical_title="Dune Messiah",
        display_title="Dune Messiah Begins Production",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=70,  # Below 80
        source_count=3,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None),
        published=False
    )
    session.add(evt)
    session.commit()

    detector = BreakingDetector()
    selector = DigestSelector()
    formatter = DigestFormatter()
    tg_formatter = TelegramFormatter()

    service = DigestService(
        breaking_detector=detector,
        digest_selector=selector,
        digest_formatter=formatter,
        telegram_formatter=tg_formatter
    )

    breaking = service.get_breaking_events(session)
    assert len(breaking) == 0
    session.close()


def test_get_breaking_events_multiple() -> None:
    """Verifies get_breaking_events returns all eligible breaking events."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # 1. Eligible breaking
    evt1 = Event(
        canonical_title="Dune 3",
        display_title="Dune Messiah Begins Production",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=90,
        source_count=3,
        last_article_at=now,
        published=False
    )
    # 2. Eligible breaking
    evt2 = Event(
        canonical_title="Wednesday",
        display_title="Wednesday Renewed",
        event_type="TV Series",
        event_pattern="RENEWAL",
        importance_score=85,
        source_count=2,
        last_article_at=now,
        published=False
    )
    # 3. Not breaking (only 1 source)
    evt3 = Event(
        canonical_title="Spiderman",
        display_title="Spiderman Releases Trailer",
        event_type="Movie",
        event_pattern="TRAILER",
        importance_score=95,
        source_count=1,
        last_article_at=now,
        published=False
    )
    # 4. Not breaking (stale, 48 hours old)
    evt4 = Event(
        canonical_title="Batman",
        display_title="Batman Announces Casting",
        event_type="Movie",
        event_pattern="CASTING",
        importance_score=90,
        source_count=3,
        last_article_at=now - timedelta(hours=48),
        published=False
    )
    session.add_all([evt1, evt2, evt3, evt4])
    session.commit()

    detector = BreakingDetector()
    selector = DigestSelector()
    formatter = DigestFormatter()
    tg_formatter = TelegramFormatter()

    service = DigestService(
        breaking_detector=detector,
        digest_selector=selector,
        digest_formatter=formatter,
        telegram_formatter=tg_formatter
    )

    breaking = service.get_breaking_events(session)
    assert len(breaking) == 2
    titles = [e.canonical_title for e in breaking]
    assert "Dune 3" in titles
    assert "Wednesday" in titles
    session.close()
