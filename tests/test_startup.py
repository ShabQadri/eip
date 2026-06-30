"""
Tests for application startup, configurations, and core stubs.
"""

import logging
from src.config.settings import settings
from src.utils.logger import setup_logger
from src.models import Article, Digest
from datetime import datetime

def test_settings_load() -> None:
    """Verifies that the Settings module loads values correctly."""
    assert settings.BASE_DIR is not None
    assert settings.LOG_LEVEL == "INFO" or settings.LOG_LEVEL is not None
    assert settings.DATABASE_URL.startswith("sqlite:///")

def test_logger_initialization() -> None:
    """Verifies that the logging utility configures standard loggers."""
    logger = setup_logger("test_eip")
    assert isinstance(logger, logging.Logger)
    assert logger.name == "test_eip"

def test_model_instantiation() -> None:
    """Verifies that basic models can be initialized as stubs."""
    item = Article(
        source_id="dummy-source",
        title="Sample Movie News",
        url="https://variety.com/news",
        description="Detailed news content",
        published_at=datetime.now(),
        hash="hash123",
        importance_score=0
    )
    assert item.title == "Sample Movie News"
    assert item.importance_score == 0.0

    digest = Digest(
        digest_type="MORNING",
        published_at=datetime.now(),
        content="Compiled Digest"
    )
    assert digest.content == "Compiled Digest"
