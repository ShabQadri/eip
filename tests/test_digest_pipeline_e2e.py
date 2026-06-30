"""
End-to-End integration and performance tests for the Digest Pipeline.
"""

import time
import sys
from datetime import datetime, timezone, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import Base
from src.models.event import Event
from src.processing.digests.digest_service import DigestService
from src.processing.digests.breaking_detector import BreakingDetector
from src.processing.digests.digest_selector import DigestSelector
from src.processing.digests.digest_formatter import DigestFormatter
from src.processing.digests.telegram_formatter import TelegramFormatter

def test_pipeline_no_events() -> None:
    """E2E Test 1: No events in DB returns empty digest message."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(current_date_override="2026-06-16"),
        telegram_formatter=TelegramFormatter()
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

def test_pipeline_single_event() -> None:
    """E2E Test 2: Single event correctly appears in the digest."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    evt = Event(
        canonical_title="Dune Messiah",
        display_title="Dune Messiah Begins Production",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=90,
        source_count=3,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None),
        published=False
    )
    session.add(evt)
    session.commit()

    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(current_date_override="2026-06-16"),
        telegram_formatter=TelegramFormatter()
    )

    result = service.generate_digest(session)
    assert "1. Dune Messiah Begins Production" in result
    assert "• Importance: 90" in result
    assert "• Sources: 3" in result
    assert "• Pattern: PRODUCTION_START" in result
    session.close()

def test_pipeline_multiple_events() -> None:
    """E2E Test 3: Multiple events appear in correct order (importance DESC, then last_article_at DESC)."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Event 1: lower importance
    evt1 = Event(
        canonical_title="Wednesday",
        display_title="Wednesday Renewed",
        event_type="TV Series",
        event_pattern="RENEWAL",
        importance_score=80,
        source_count=2,
        last_article_at=now,
        published=False
    )
    # Event 2: higher importance
    evt2 = Event(
        canonical_title="Dune Messiah",
        display_title="Dune Messiah Begins Production",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=95,
        source_count=3,
        last_article_at=now - timedelta(hours=1),
        published=False
    )
    # Event 3: same importance as Event 2, but older
    evt3 = Event(
        canonical_title="Batman",
        display_title="Batman Announces Casting",
        event_type="Movie",
        event_pattern="CASTING",
        importance_score=95,
        source_count=4,
        last_article_at=now - timedelta(hours=2),
        published=False
    )

    session.add_all([evt1, evt2, evt3])
    session.commit()

    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(current_date_override="2026-06-16"),
        telegram_formatter=TelegramFormatter()
    )

    result = service.generate_digest(session)
    
    # Order should be: evt2 (95, 1h ago) -> evt3 (95, 2h ago) -> evt1 (80, now)
    pos_dune = result.find("1. Dune Messiah Begins Production")
    pos_batman = result.find("2. Batman Announces Casting")
    pos_wednesday = result.find("3. Wednesday Renewed")

    assert pos_dune != -1
    assert pos_batman != -1
    assert pos_wednesday != -1
    assert pos_dune < pos_batman < pos_wednesday
    session.close()

def test_pipeline_max_12_events() -> None:
    """E2E Test 4: More than 12 events are capped at 12 events."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    events = [
        Event(
            canonical_title=f"Movie {i}",
            display_title=f"Movie {i} Sets Release Date",
            event_type="Movie",
            event_pattern="RELEASE_DATE",
            importance_score=80 + (i % 10),
            source_count=2,
            last_article_at=now,
            published=False
        )
        for i in range(1, 16)
    ]
    session.add_all(events)
    session.commit()

    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(current_date_override="2026-06-16"),
        telegram_formatter=TelegramFormatter()
    )

    result = service.generate_digest(session)
    # The formatted digest has exactly 12 items
    assert "12. " in result
    assert "13. " not in result
    session.close()

def test_pipeline_telegram_safe() -> None:
    """E2E Test 5: Verify that telegram_safe=True correctly escapes special characters."""
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

    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(current_date_override="2026-06-16"),
        telegram_formatter=TelegramFormatter()
    )

    result = service.generate_digest(session, telegram_safe=True)
    # Characters like '-' and '!' and '.' must be escaped
    assert r"Spider\-Man: Brand New Day\!" in result
    assert r"🗓 2026\-06\-16" in result
    session.close()

def test_pipeline_breaking_events() -> None:
    """E2E Test 6: Verify get_breaking_events returns only eligible breaking events."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    # Event A: Eligible breaking (importance=95, sources=3, age=1 hour)
    evt_a = Event(
        canonical_title="Event A",
        display_title="Event A Happens",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=95,
        source_count=3,
        last_article_at=now - timedelta(hours=1),
        published=False
    )
    # Event B: Ineligible (importance=75)
    evt_b = Event(
        canonical_title="Event B",
        display_title="Event B Happens",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=75,
        source_count=3,
        last_article_at=now,
        published=False
    )

    session.add_all([evt_a, evt_b])
    session.commit()

    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(),
        telegram_formatter=TelegramFormatter()
    )

    breaking = service.get_breaking_events(session)
    assert len(breaking) == 1
    assert breaking[0].canonical_title == "Event A"
    session.close()

def test_pipeline_stage_flow_validation() -> None:
    """E2E Test 7: Trace pipeline flow validation to verify inputs/outputs at every stage."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    evt = Event(
        canonical_title="Dune 3",
        display_title="Dune Messiah",
        event_type="Movie",
        event_pattern="PRODUCTION_START",
        importance_score=90,
        source_count=2,
        last_article_at=datetime.now(timezone.utc).replace(tzinfo=None),
        published=False
    )
    session.add(evt)
    session.commit()

    # Stage 1: Selector
    selector = DigestSelector()
    selected_events = selector.select_events_for_digest(session)
    assert len(selected_events) == 1
    assert selected_events[0].canonical_title == "Dune 3"

    # Stage 2: Formatter
    formatter = DigestFormatter(current_date_override="2026-06-16")
    formatted_text = formatter.format_digest(selected_events)
    assert "1. Dune Messiah" in formatted_text
    assert "Importance: 90" in formatted_text

    # Stage 3: Telegram Formatter
    tg = TelegramFormatter()
    telegram_text = tg.format_digest_message(formatted_text)
    assert r"1\. Dune Messiah" in telegram_text

    # Stage 4: Digest Service Orchestration
    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=selector,
        digest_formatter=formatter,
        telegram_formatter=tg
    )
    res_raw = service.generate_digest(session, telegram_safe=False)
    res_tg = service.generate_digest(session, telegram_safe=True)

    assert res_raw == formatted_text
    assert res_tg == telegram_text
    session.close()

def test_pipeline_performance() -> None:
    """E2E Test 8: Performance verification using 1000 fake events."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    
    # Generate 1000 fake events
    print("Generating 1000 fake events...")
    events = [
        Event(
            canonical_title=f"Movie {i}",
            display_title=f"Movie {i} Begins Production",
            event_type="Movie",
            event_pattern="PRODUCTION_START",
            importance_score=70 + (i % 25),  # 70 to 94
            source_count=2,
            last_article_at=now,
            published=False
        )
        for i in range(1, 1001)
    ]
    session.add_all(events)
    session.commit()

    service = DigestService(
        breaking_detector=BreakingDetector(),
        digest_selector=DigestSelector(),
        digest_formatter=DigestFormatter(),
        telegram_formatter=TelegramFormatter()
    )

    # Measure execution time
    start_time = time.perf_counter()
    result = service.generate_digest(session, telegram_safe=True)
    end_time = time.perf_counter()
    execution_time = end_time - start_time

    print(f"E2E Performance: 1000 events took {execution_time:.4f} seconds.")
    
    assert execution_time < 2.0  # Must be under 2 seconds
    assert len(result) > 0
    session.close()
