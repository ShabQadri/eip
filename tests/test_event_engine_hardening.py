"""
Hardening tests for EIP Event Engine and Smart Deduplication.
"""

from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import Base
from src.models.source import Source
from src.models.article import Article
from src.models.event import Event
from src.processing.events.event_service import EventService

def test_cross_franchise_false_positive() -> None:
    """Articles from different franchises should not merge."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # Seed variety source
    src = Source(id="src-v", name="Variety", domain="variety.com", rss_url="url1", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
    db.add(src)
    db.commit()

    service = EventService()

    art1 = Article(
        source_id="src-v",
        title="Dune Trailer Released",
        description="First teaser for Dune Part Two.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="h1",
        url="url1"
    )
    art2 = Article(
        source_id="src-v",
        title="Foundation Trailer Released",
        description="First teaser for Foundation Season Three.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="h2",
        url="url2"
    )
    db.add(art1)
    db.add(art2)
    db.flush()

    e1 = service.process_article(db, art1)
    e2 = service.process_article(db, art2)

    db.commit()

    # Expected: 2 separate events
    assert e1 is not None
    assert e2 is not None
    assert e1.id != e2.id
    assert e1.canonical_title != e2.canonical_title

    # Expected: Similarity score below merge threshold
    score = service.similarity_engine.calculate_similarity(
        title1=art1.title,
        title2=art2.title,
        desc1=art1.description,
        desc2=art2.description
    )
    assert score < 85.0

    db.close()


def test_same_franchise_different_pattern() -> None:
    """Articles from the same franchise but with different event milestones should not merge."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    src = Source(id="src-v", name="Variety", domain="variety.com", rss_url="url1", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
    db.add(src)
    db.commit()

    service = EventService()

    art1 = Article(
        source_id="src-v",
        title="Dune Begins Filming",
        description="Production starts on Denis Villeneuve's film.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="h1",
        url="url1"
    )
    art2 = Article(
        source_id="src-v",
        title="Dune Trailer Released",
        description="First look at Dune.",
        importance_score=85,
        published_at=datetime.now(timezone.utc),
        hash="h2",
        url="url2"
    )
    db.add(art1)
    db.add(art2)
    db.flush()

    e1 = service.process_article(db, art1)
    e2 = service.process_article(db, art2)

    db.commit()

    # Expected: 2 separate events with different patterns
    assert e1 is not None
    assert e2 is not None
    assert e1.id != e2.id
    assert e1.event_pattern == "PRODUCTION_START"
    assert e2.event_pattern == "TRAILER"
    assert e1.canonical_title == "Dune"
    assert e2.canonical_title == "Dune"

    score = service.similarity_engine.calculate_similarity(
        title1=art1.title,
        title2=art2.title,
        desc1=art1.description,
        desc2=art2.description
    )
    assert score == 0.0

    db.close()


def test_recurring_announcements() -> None:
    """Season renewals from different years/seasons should not merge."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    src = Source(id="src-v", name="Variety", domain="variety.com", rss_url="url1", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
    db.add(src)
    db.commit()

    service = EventService()

    art1 = Article(
        source_id="src-v",
        title="Wednesday Renewed for Season 2 (2023)",
        description="Netflix greenlits second season of Wednesday.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="h1",
        url="url1"
    )
    art2 = Article(
        source_id="src-v",
        title="Wednesday Renewed for Season 3 (2026)",
        description="Netflix greenlits third season of Wednesday.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="h2",
        url="url2"
    )
    db.add(art1)
    db.add(art2)
    db.flush()

    e1 = service.process_article(db, art1)
    e2 = service.process_article(db, art2)

    db.commit()

    # Expected: 2 separate events
    assert e1 is not None
    assert e2 is not None
    assert e1.id != e2.id
    assert e1.canonical_title == "Wednesday"
    assert e2.canonical_title == "Wednesday"
    assert e1.season_number == 2
    assert e1.event_year == 2023
    assert e2.season_number == 3
    assert e2.event_year == 2026

    # Expected: Separate aliases
    assert "Wednesday Renewed for Season 2 (2023)" in e1.aliases_json or e1.canonical_title == "Wednesday Renewed for Season 2 (2023)"
    assert "Wednesday Renewed for Season 3 (2026)" in e2.aliases_json or e2.canonical_title == "Wednesday Renewed for Season 3 (2026)"
    assert not set(e1.aliases_json or []).intersection(set(e2.aliases_json or []))

    # Expected: Similarity score is 0.0 because of non-equal digit sets (season 2 vs 3, 2023 vs 2026)
    score = service.similarity_engine.calculate_similarity(
        title1=art1.title,
        title2=art2.title,
        desc1=art1.description,
        desc2=art2.description
    )
    assert score == 0.0

    db.close()


def test_source_counting_and_importance() -> None:
    """Verifies event source counts and dynamic importance score calculations."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    src1 = Source(id="src-v", name="Variety", domain="variety.com", rss_url="url1", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
    src2 = Source(id="src-d", name="Deadline", domain="deadline.com", rss_url="url2", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
    db.add(src1)
    db.add(src2)
    db.commit()

    service = EventService()

    # Three duplicate articles: Variety, Deadline, Variety
    art1 = Article(
        source_id="src-v",
        title="Dune Messiah Begins Filming",
        description="Denis Villeneuve starts production.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="h1",
        url="url1"
    )
    art2 = Article(
        source_id="src-d",
        title="Dune 3 Starts Production",
        description="Dune franchise enters production.",
        importance_score=85,
        published_at=datetime.now(timezone.utc),
        hash="h2",
        url="url2"
    )
    art3 = Article(
        source_id="src-v",
        title="Cameras Roll on Dune Messiah",
        description="Cameras roll on Dune Messiah.",
        importance_score=90,
        published_at=datetime.now(timezone.utc),
        hash="h3",
        url="url3"
    )
    db.add(art1)
    db.add(art2)
    db.add(art3)
    db.flush()

    e1 = service.process_article(db, art1)
    e2 = service.process_article(db, art2)
    e3 = service.process_article(db, art3)

    db.commit()

    # Verify matching
    assert e1 is not None
    assert e2 is not None
    assert e3 is not None
    assert e1.id == e2.id == e3.id

    # Verify counts
    assert e1.article_count == 3
    assert e1.source_count == 2
    assert set(e1.source_domains_json) == {"variety.com", "deadline.com"}

    # Verify event importance calculation:
    # max(80, 85, 90) + 3 * (2 - 1) = 93
    assert e1.importance_score == 93

    db.close()


def test_event_fragmentation_prevention() -> None:
    """Verifies that years in trailers do not fragment events, whereas renewals still do."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    src = Source(id="src-v", name="Variety", domain="variety.com", rss_url="url1", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
    db.add(src)
    db.commit()

    service = EventService()

    # 1. Dune Trailer Released (2026) vs Dune Trailer Released (2027) -> Same event
    art_trailer1 = Article(
        source_id="src-v",
        title="Dune Trailer Released (2026)",
        description="First look in 2026.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="t1",
        url="url_t1",
        category="Movie"
    )
    art_trailer2 = Article(
        source_id="src-v",
        title="Dune Trailer Released (2027)",
        description="Follow-up look in 2027.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="t2",
        url="url_t2",
        category="Movie"
    )
    db.add(art_trailer1)
    db.add(art_trailer2)
    db.flush()

    e_t1 = service.process_article(db, art_trailer1)
    e_t2 = service.process_article(db, art_trailer2)

    assert e_t1 is not None
    assert e_t2 is not None
    # Expected: Same event
    assert e_t1.id == e_t2.id
    # Clean canonical title
    assert e_t1.canonical_title == "Dune"
    # season_number and event_year must remain NULL
    assert e_t1.season_number is None
    assert e_t1.event_year is None

    # 2. Wednesday Renewed Season 2 (2023) vs Wednesday Renewed Season 3 (2026) -> Separate events
    art_renew1 = Article(
        source_id="src-v",
        title="Wednesday Renewed Season 2 (2023)",
        description="Netflix greenlits second season of Wednesday.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="r1",
        url="url_r1",
        category="TV Series"
    )
    art_renew2 = Article(
        source_id="src-v",
        title="Wednesday Renewed Season 3 (2026)",
        description="Netflix greenlits third season of Wednesday.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="r2",
        url="url_r2",
        category="TV Series"
    )
    db.add(art_renew1)
    db.add(art_renew2)
    db.flush()

    e_r1 = service.process_article(db, art_renew1)
    e_r2 = service.process_article(db, art_renew2)

    assert e_r1 is not None
    assert e_r2 is not None
    # Expected: Separate events
    assert e_r1.id != e_r2.id
    # Clean canonical title
    assert e_r1.canonical_title == "Wednesday"
    assert e_r2.canonical_title == "Wednesday"
    # Extracted fields
    assert e_r1.season_number == 2
    assert e_r1.event_year == 2023
    assert e_r2.season_number == 3
    assert e_r2.event_year == 2026

    db.close()


def test_display_title_generation() -> None:
    """Verifies display_title generation and automatic population in EventBuilder."""
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    src = Source(id="src-v", name="Variety", domain="variety.com", rss_url="url1", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
    db.add(src)
    db.commit()

    service = EventService()

    # 1. Dune Trailer
    art1 = Article(
        source_id="src-v",
        title="Dune Trailer Released",
        description="First teaser for Dune.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="dt1",
        url="url_dt1",
        category="Movie"
    )
    e1 = service.process_article(db, art1)

    # 2. Dune Production Start
    art2 = Article(
        source_id="src-v",
        title="Dune Begins Filming",
        description="Production starts on Dune.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="dp1",
        url="url_dp1",
        category="Movie"
    )
    e2 = service.process_article(db, art2)

    # 3. Wednesday Season 2 Renewal
    art3 = Article(
        source_id="src-v",
        title="Wednesday Renewed for Season 2",
        description="Wednesday gets season 2.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="wr1",
        url="url_wr1",
        category="TV Series"
    )
    e3 = service.process_article(db, art3)

    # 4. Wednesday Season 3 Renewal
    art4 = Article(
        source_id="src-v",
        title="Wednesday Renewed for Season 3",
        description="Wednesday gets season 3.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="wr2",
        url="url_wr2",
        category="TV Series"
    )
    e4 = service.process_article(db, art4)

    # 5. Dune Sets Release Date
    art5 = Article(
        source_id="src-v",
        title="Dune release date confirmed",
        description="Sets release date.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="dr1",
        url="url_dr1",
        category="Movie"
    )
    e5 = service.process_article(db, art5)

    # 6. Dune Announces Casting
    art6 = Article(
        source_id="src-v",
        title="Florence Pugh joins cast of Dune",
        description="Boards the sequel.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="dc1",
        url="url_dc1",
        category="Movie"
    )
    e6 = service.process_article(db, art6)

    # 7. Dune Wins Award
    art7 = Article(
        source_id="src-v",
        title="Dune wins golden globe",
        description="Golden globe awards.",
        importance_score=80,
        published_at=datetime.now(timezone.utc),
        hash="da1",
        url="url_da1",
        category="Movie"
    )
    e7 = service.process_article(db, art7)

    db.commit()

    # Assertions for preservation of clean canonical titles
    assert e1.canonical_title == "Dune"
    assert e1.display_title == "Dune Releases Trailer"
    assert e1.event_pattern == "TRAILER"

    assert e2.canonical_title == "Dune"
    assert e2.display_title == "Dune Begins Production"
    assert e2.event_pattern == "PRODUCTION_START"

    assert e3.canonical_title == "Wednesday"
    assert e3.display_title == "Wednesday Renewed"
    assert e3.event_pattern == "RENEWAL"
    assert e3.season_number == 2

    assert e4.canonical_title == "Wednesday"
    assert e4.display_title == "Wednesday Renewed"
    assert e4.event_pattern == "RENEWAL"
    assert e4.season_number == 3

    assert e5.canonical_title == "Dune"
    assert e5.display_title == "Dune Sets Release Date"
    assert e5.event_pattern == "RELEASE_DATE"

    assert e6.canonical_title == "Dune"
    assert e6.display_title == "Dune Announces Casting"
    assert e6.event_pattern == "CASTING"

    assert e7.canonical_title == "Dune"
    assert e7.display_title == "Dune Wins Award"
    assert e7.event_pattern == "AWARDS"

    db.close()


