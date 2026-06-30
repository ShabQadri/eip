"""
Tests for TelegramFormatter.
"""

from src.processing.digests.telegram_formatter import TelegramFormatter
from src.models.event import Event

def test_telegram_formatter_initialization() -> None:
    """Verifies TelegramFormatter initializes correctly."""
    formatter = TelegramFormatter()
    assert isinstance(formatter, TelegramFormatter)

def test_markdown_escaping() -> None:
    """Verifies all special Telegram MarkdownV2 characters are escaped."""
    formatter = TelegramFormatter()
    # Special characters to escape: \ _ * [ ] ( ) ~ ` > # + - = | { } . !
    input_text = r"Hello_World*This[Is](Telegram)~`>#+-=|{}." + "!"
    expected = (
        r"Hello\_World\*This\[Is\]\(Telegram\)\~\`\>\#\+\-\=\|\{\}\.\!"
    )
    result = formatter.escape_markdown_v2(input_text)
    assert result == expected

def test_breaking_alert_formatting() -> None:
    """Verifies format_breaking_alert structures the message correctly with escaped fields."""
    formatter = TelegramFormatter()
    event = Event(
        canonical_title="Dune Messiah",
        display_title="Dune Messiah Begins Production",
        importance_score=93,
        source_count=2
    )
    result = formatter.format_breaking_alert(event)
    # The hashtags #Entertainment and #Breaking must be escaped as well as the text
    expected = (
        "🚨 BREAKING\n"
        "\n"
        "🎬 Dune Messiah Begins Production\n"
        "\n"
        "Importance: 93\n"
        "Sources: 2\n"
        "\n"
        r"\#Entertainment \#Breaking"
    )
    assert result == expected

def test_breaking_alert_missing_values() -> None:
    """Verifies format_breaking_alert uses fallback values when importance or sources are None."""
    formatter = TelegramFormatter()
    event = Event(
        canonical_title="Dune Messiah",
        display_title="Dune Messiah Begins Production",
        importance_score=None,
        source_count=None
    )
    result = formatter.format_breaking_alert(event)
    expected = (
        "🚨 BREAKING\n"
        "\n"
        "🎬 Dune Messiah Begins Production\n"
        "\n"
        "Importance: N/A\n"
        "Sources: 1\n"
        "\n"
        r"\#Entertainment \#Breaking"
    )
    assert result == expected

def test_digest_formatting() -> None:
    """Verifies format_digest_message correctly escapes a plain text digest."""
    formatter = TelegramFormatter()
    digest_text = (
        "🎬 Entertainment Intelligence Digest\n"
        "🗓 2026-06-16\n"
        "\n"
        "1. Dune Messiah Begins Production\n"
        "   • Importance: 85\n"
        "   • Sources: 3\n"
        "   • Pattern: PRODUCTION_START"
    )
    result = formatter.format_digest_message(digest_text)
    # Verify '.' and '-' are escaped
    assert r"🗓 2026\-06\-16" in result
    assert r"1\. Dune Messiah" in result
    assert r"Importance: 85" in result
    assert r"Pattern: PRODUCTION\_START" in result

def test_special_characters_handling() -> None:
    """Verifies titles with special characters like 'Dune: Part Two!' and 'Spider-Man: Brand New Day' are escaped and do not break MarkdownV2 formatting."""
    formatter = TelegramFormatter()
    event1 = Event(
        canonical_title="Dune 2",
        display_title="Dune: Part Two!",
        importance_score=95,
        source_count=4
    )
    result1 = formatter.format_breaking_alert(event1)
    # Check that '!' is escaped
    assert r"Dune: Part Two\!" in result1
    
    event2 = Event(
        canonical_title="Spider-Man",
        display_title="Spider-Man: Brand New Day",
        importance_score=88,
        source_count=3
    )
    result2 = formatter.format_breaking_alert(event2)
    # Check that '-' is escaped
    assert r"Spider\-Man: Brand New Day" in result2
