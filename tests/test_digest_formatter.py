"""
Tests for DigestFormatter.
"""

from src.processing.digests.digest_formatter import DigestFormatter
from src.models.event import Event

def test_digest_formatter_initialization() -> None:
    """Verifies DigestFormatter initializes correctly."""
    formatter = DigestFormatter()
    assert isinstance(formatter, DigestFormatter)

def test_format_digest_empty() -> None:
    """Verifies formatting 0 events returns the empty digest message."""
    formatter = DigestFormatter(current_date_override="2026-06-16")
    result = formatter.format_digest([])
    expected = (
        "🎬 Entertainment Intelligence Digest\n"
        "🗓 2026-06-16\n"
        "\n"
        "No major entertainment developments at this time."
    )
    assert result == expected

def test_format_digest_single_event() -> None:
    """Verifies formatting 1 event correctly formats the title, importance, sources, and pattern."""
    formatter = DigestFormatter(current_date_override="2026-06-16")
    event = Event(
        canonical_title="Dune Messiah",
        display_title="Dune Messiah Begins Production",
        event_pattern="PRODUCTION_START",
        importance_score=85,
        source_count=3
    )
    result = formatter.format_digest([event])
    expected = (
        "🎬 Entertainment Intelligence Digest\n"
        "🗓 2026-06-16\n"
        "\n"
        "1. Dune Messiah Begins Production\n"
        "   • Importance: 85\n"
        "   • Sources: 3\n"
        "   • Pattern: PRODUCTION_START"
    )
    assert result == expected

def test_format_digest_max_12_events() -> None:
    """Verifies formatting exactly 12 events works properly."""
    formatter = DigestFormatter(current_date_override="2026-06-16")
    events = [
        Event(
            canonical_title=f"Movie {i}",
            display_title=f"Movie {i} Sets Release Date",
            event_pattern="RELEASE_DATE",
            importance_score=70 + i,
            source_count=2
        )
        for i in range(1, 13)
    ]
    result = formatter.format_digest(events)
    # Check that we have exactly 12 items formatted
    assert "12. Movie 12 Sets Release Date" in result
    
    # Verify count of entries
    lines = result.split("\n")
    # Header takes 2 lines, plus 5 lines per event (1 blank + 4 content lines)
    # 2 + 12 * 5 = 62 lines
    assert len(lines) == 62

def test_format_digest_more_than_12_events() -> None:
    """Verifies that format_digest caps the output at 12 events and does not reorder."""
    formatter = DigestFormatter(current_date_override="2026-06-16")
    events = [
        Event(
            canonical_title=f"Movie {i}",
            display_title=f"Movie {i} Announces Casting",
            event_pattern="CASTING",
            importance_score=80,
            source_count=2
        )
        for i in range(1, 16)
    ]
    result = formatter.format_digest(events)
    # Check that item 12 is present, but item 13 and onward are omitted
    assert "12. Movie 12 Announces Casting" in result
    assert "13. Movie 13 Announces Casting" not in result
    assert "14. Movie 14" not in result

def test_format_digest_missing_values() -> None:
    """Verifies fallback values are correctly used when pattern, source_count, or importance are missing."""
    formatter = DigestFormatter(current_date_override="2026-06-16")
    event = Event(
        canonical_title="Spiderman 4",
        display_title="Spiderman 4 Announces Casting",
        event_pattern=None,
        importance_score=None,
        source_count=None
    )
    result = formatter.format_digest([event])
    expected = (
        "🎬 Entertainment Intelligence Digest\n"
        "🗓 2026-06-16\n"
        "\n"
        "1. Spiderman 4 Announces Casting\n"
        "   • Importance: N/A\n"
        "   • Sources: 1\n"
        "   • Pattern: Unknown"
    )
    assert result == expected

def test_format_digest_verify_display_title_used() -> None:
    """Verifies that display_title is always used instead of canonical_title."""
    formatter = DigestFormatter(current_date_override="2026-06-16")
    event = Event(
        canonical_title="Dune",
        display_title="Dune Releases Trailer",
        event_pattern="TRAILER",
        importance_score=90,
        source_count=5
    )
    result = formatter.format_digest([event])
    assert "Dune Releases Trailer" in result
    assert "1. Dune\n" not in result
