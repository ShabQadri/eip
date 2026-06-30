"""
Tests for BreakingDetector.
"""

from datetime import datetime, timezone, timedelta
from src.processing.digests.breaking_detector import BreakingDetector
from src.models.event import Event

def test_breaking_detector_initialization() -> None:
    """Verifies BreakingDetector initializes correctly with default values."""
    detector = BreakingDetector()
    assert detector.breaking_threshold == 80

    custom_detector = BreakingDetector(breaking_threshold=90)
    assert custom_detector.breaking_threshold == 90

def test_breaking_detector_is_breaking_scenarios() -> None:
    """Verifies is_breaking logic across multiple scenarios."""
    detector = BreakingDetector(breaking_threshold=80)
    ref_time = datetime.now(timezone.utc)

    # Case 1: importance=90, sources=3, age=1 hour -> Expected: True
    e1 = Event(
        canonical_title="Test Event 1",
        event_type="General",
        importance_score=90,
        source_count=3,
        last_article_at=ref_time.replace(tzinfo=None) - timedelta(hours=1)
    )
    assert detector.is_breaking(e1, reference_time=ref_time) is True

    # Case 2: importance=75, sources=3 -> Expected: False
    e2 = Event(
        canonical_title="Test Event 2",
        event_type="General",
        importance_score=75,
        source_count=3,
        last_article_at=ref_time.replace(tzinfo=None) - timedelta(hours=1)
    )
    assert detector.is_breaking(e2, reference_time=ref_time) is False

    # Case 3: importance=95, sources=1 -> Expected: False
    e3 = Event(
        canonical_title="Test Event 3",
        event_type="General",
        importance_score=95,
        source_count=1,
        last_article_at=ref_time.replace(tzinfo=None) - timedelta(hours=1)
    )
    assert detector.is_breaking(e3, reference_time=ref_time) is False

    # Case 4: importance=95, sources=3, age=48 hours -> Expected: False
    e4 = Event(
        canonical_title="Test Event 4",
        event_type="General",
        importance_score=95,
        source_count=3,
        last_article_at=ref_time.replace(tzinfo=None) - timedelta(hours=48)
    )
    assert detector.is_breaking(e4, reference_time=ref_time) is False

    # Case 5: pattern=REVIEWS -> Expected: False
    e5 = Event(
        canonical_title="Test Event 5",
        event_type="General",
        event_pattern="REVIEWS",
        importance_score=90,
        source_count=3,
        last_article_at=ref_time.replace(tzinfo=None) - timedelta(hours=1)
    )
    assert detector.is_breaking(e5, reference_time=ref_time) is False

def test_breaking_detector_should_ignore_pattern() -> None:
    """Verifies pattern ignoring behavior."""
    detector = BreakingDetector()
    assert detector.should_ignore_pattern("REVIEWS") is True
    assert detector.should_ignore_pattern("box_office_daily") is True
    assert detector.should_ignore_pattern("GALLERY") is True
    assert detector.should_ignore_pattern("photo") is True
    assert detector.should_ignore_pattern("TRAILER") is False
    assert detector.should_ignore_pattern(None) is False
