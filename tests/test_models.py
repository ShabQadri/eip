"""
Unit tests for domain schemas and model parsing verification.
"""

from datetime import datetime
import pytest
from pydantic import ValidationError
from src.models.schemas.source_schema import SourceCreate, SourceRead
from src.models.schemas.event_schema import EventCreate, EventRead
from src.models.schemas.article_schema import ArticleCreate, ArticleRead
from src.models.schemas.review_schema import ReviewConsensusCreate, ReviewConsensusRead
from src.models.schemas.digest_schema import DigestCreate, DigestRead
from src.models.schemas.published_post_schema import PublishedPostCreate, PublishedPostRead
from src.models.schemas.settings_schema import SettingsCreate, SettingsRead

def test_source_schema_validation() -> None:
    """Verifies Pydantic validation for Source schema input and outputs."""
    raw_input = {
        "name": "Variety",
        "domain": "variety.com",
        "rss_url": "https://variety.com/feed",
        "source_type": "RSS",
        "source_tier": 1,
        "policy": "SUMMARY_ALLOWED",
        "enabled": True,
        "trust_score": 90
    }
    
    # Validation passes on valid inputs
    source_in = SourceCreate(**raw_input)
    assert source_in.name == "Variety"
    assert source_in.trust_score == 90

    # Validation fails on invalid inputs
    invalid_input = raw_input.copy()
    invalid_input["source_tier"] = 5  # Tier must be between 1 and 3
    with pytest.raises(ValidationError):
        SourceCreate(**invalid_input)

    # Output schema serialization
    read_data = raw_input.copy()
    read_data.update({
        "id": "12345678-1234-1234-1234-1234567890ab",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    })
    source_out = SourceRead(**read_data)
    assert source_out.id == "12345678-1234-1234-1234-1234567890ab"

def test_event_schema_validation() -> None:
    """Verifies Pydantic validation for Event schemas."""
    raw_input = {
        "canonical_title": "Dune: Part Two",
        "event_type": "Release Dates",
        "importance_score": 85,
        "region": "GLOBAL",
        "franchise": "Dune",
        "status": "RELEASED",
        "is_gossip": False,
        "is_featured": True
    }
    
    event_in = EventCreate(**raw_input)
    assert event_in.canonical_title == "Dune: Part Two"
    assert event_in.is_featured is True

def test_article_schema_validation() -> None:
    """Verifies Pydantic validation for Article schemas."""
    raw_input = {
        "source_id": "source-uuid",
        "event_id": "event-uuid",
        "title": "Dune Part Two Sets Digital Release Date",
        "url": "https://variety.com/dune-digital-date",
        "description": "Warner Bros. has announced the release date.",
        "author": "John Doe",
        "published_at": datetime.now(),
        "hash": "a1b2c3d4e5f6g7h8i9j0",
        "category": "Streaming",
        "importance_score": 75,
        "region": "GLOBAL",
        "is_gossip": False,
        "is_verified": True,
        "status": "new"
    }
    
    article_in = ArticleCreate(**raw_input)
    assert article_in.title == "Dune Part Two Sets Digital Release Date"
    assert article_in.importance_score == 75

def test_settings_schema_validation() -> None:
    """Verifies Pydantic validation for Settings schemas."""
    raw_input = {
        "article_retention_days": 90,
        "image_retention_days": 180,
        "log_retention_days": 30,
        "breaking_threshold": 80,
        "digest_threshold": 60,
        "max_articles_per_digest": 12,
        "cleanup_hour": 2,
        "keep_images": True
    }
    
    settings_in = SettingsCreate(**raw_input)
    assert settings_in.cleanup_hour == 2
    assert settings_in.keep_images is True

    # Validate limits
    invalid_input = raw_input.copy()
    invalid_input["cleanup_hour"] = 25  # Invalid hour
    with pytest.raises(ValidationError):
        SettingsCreate(**invalid_input)
