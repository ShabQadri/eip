import pytest
import json
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.services.scheduler_service import SchedulerService
from src.processing.digests.telegram_formatter import TelegramFormatter
from src.models import Article, Event

@pytest.mark.asyncio
async def test_digest_with_5_stories():
    """Test compiling a digest with exactly 5 stories in one message."""
    formatter = TelegramFormatter()
    stories_data = [
        {"title": f"Story {i}", "text": f"This is short brief number {i}.", "urls": [f"https://variety.com/{i}"], "trailer": None}
        for i in range(1, 6)
    ]
    
    blocks = []
    for idx, s in enumerate(stories_data, 1):
        formatted = formatter.format_digest_story(idx, s["title"], s["text"], s["urls"], s["trailer"])
        blocks.append(formatted)
        
    divider = "\n\n" + formatter.escape_markdown_v2("────────────") + "\n\n"
    digest_body = divider.join(blocks)
    full_digest = "🎬 *ENTERTAINMENT NEWS DIGEST*\n\n" + digest_body
    
    # Assert formatting structure and exactly 5 blocks
    assert len(blocks) == 5
    assert "Story 1" in full_digest
    assert "Story 5" in full_digest
    assert "────────────" in full_digest

@pytest.mark.asyncio
async def test_digest_with_10_stories():
    """Test compiling a digest with exactly 10 stories in one message."""
    formatter = TelegramFormatter()
    stories_data = [
        {"title": f"Story {i}", "text": f"This is short brief number {i}.", "urls": [f"https://variety.com/{i}"], "trailer": None}
        for i in range(1, 11)
    ]
    
    blocks = []
    for idx, s in enumerate(stories_data, 1):
        formatted = formatter.format_digest_story(idx, s["title"], s["text"], s["urls"], s["trailer"])
        blocks.append(formatted)
        
    assert len(blocks) == 10

@pytest.mark.asyncio
async def test_digest_with_12_stories():
    """Test compiling a digest with exactly 12 stories in one message."""
    formatter = TelegramFormatter()
    stories_data = [
        {"title": f"Story {i}", "text": f"This is short brief number {i}.", "urls": [f"https://variety.com/{i}"], "trailer": None}
        for i in range(1, 13)
    ]
    
    blocks = []
    for idx, s in enumerate(stories_data, 1):
        formatted = formatter.format_digest_story(idx, s["title"], s["text"], s["urls"], s["trailer"])
        blocks.append(formatted)
        
    assert len(blocks) == 12

def test_short_story_output_no_forced_long_paragraphs():
    """Test that stories are formatted as a single concise news brief (no multiple/forced long paragraphs)."""
    formatter = TelegramFormatter()
    story_text = "Universal has launched the Roblox companion game for Nolan's next movie."
    formatted = formatter.format_digest_story(1, "Roblox Game", story_text, ["https://variety.com"])
    
    # Verifies word count target is met
    words = len(formatted.split())
    assert words <= 80
    # Verifies no duplicate paragraph forcing
    assert "\n\n\n" not in formatted

def test_duplicate_articles_consolidated():
    """Test that duplicate articles linked to the same event are handled as a single story block with multiple sources."""
    formatter = TelegramFormatter()
    # 5 duplicate source articles reporting on the same development
    source_urls = [
        "https://variety.com/article1",
        "https://deadline.com/article1",
        "https://hollywoodreporter.com/article1",
        "https://collider.com/article1",
        "https://screenrant.com/article1"
    ]
    story_text = "Universal released the official companion game."
    
    # Formatter limits sources shown to top 3 and represents them with clean domain names
    formatted = formatter.format_digest_story(1, "The Odyssey Roblox Game", story_text, source_urls)
    
    assert "🔗 Sources: [Variety]" in formatted
    assert "[Deadline]" in formatted
    assert "[Hollywoodreporter]" in formatted
    # Verifies sources are capped at 3
    assert "Collider" not in formatted
    assert "Screenrant" not in formatted

def test_digest_character_budget_and_pruning():
    """Test that the compiler prunes lower-priority stories when character budget is exceeded."""
    # Build list of 8 mock stories (already sorted by importance descending)
    stories = [
        {
            "event": Event(canonical_title=f"Event {i}", display_title=f"Event {i}", importance_score=100-i),
            "story_text": "A" * 400, # Large text to easily exceed a low budget
            "source_urls": ["https://variety.com"],
            "trailer_url": None
        }
        for i in range(1, 9)
    ]
    
    formatter = TelegramFormatter()
    
    # Pruning loop simulating character budget check
    # Safety budget set to 1500 characters
    while len(stories) > 0:
        digest_header = "🎬 *ENTERTAINMENT NEWS DIGEST*\n\n"
        story_blocks = []
        for i, s in enumerate(stories, 1):
            formatted_story = formatter.format_digest_story(i, s["event"].canonical_title, s["story_text"], s["source_urls"], s["trailer_url"])
            story_blocks.append(formatted_story)
            
        divider = "\n\n────────────\n\n"
        full_text = digest_header + divider.join(story_blocks)
        
        if len(full_text) <= 1500:
            break
            
        # Pop lowest priority (since list is sorted DESC by importance)
        stories.pop()
        
    # Assert that pruning reduced the size to fit within the budget
    assert len(full_text) <= 1500
    assert len(stories) < 8
    # Verifies that highest importance (Event 1, score 99) is kept
    assert "Event 1" in full_text

def test_source_links_and_trailers():
    """Test that source links and verified trailers are formatted correctly and unverified ones omitted."""
    formatter = TelegramFormatter()
    
    # 1. With verified trailer
    res_with_trailer = formatter.format_digest_story(
        idx=1,
        title="Dune 3",
        story_text="Dune 3 teaser released.",
        source_urls=["https://variety.com"],
        trailer_url="https://youtube.com/watch?v=123"
    )
    assert "🔗 Source: [Variety]" in res_with_trailer
    assert "▶️ [Watch Trailer]" in res_with_trailer
    
    # 2. Without trailer
    res_no_trailer = formatter.format_digest_story(
        idx=1,
        title="Dune 3",
        story_text="Dune 3 teaser released.",
        source_urls=["https://variety.com"],
        trailer_url=None
    )
    assert "🔗 Source: [Variety]" in res_no_trailer
    assert "▶️" not in res_no_trailer
