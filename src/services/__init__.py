"""
Services package defining interfaces for core system operations.
Uses Protocol-based definitions to support modularity and dependency injection.
"""

from typing import Protocol
from src.models import Article, Digest

class FeedService(Protocol):
    """
    Interface for RSS ingestion operations.
    """
    async def fetch_and_store_feeds(self) -> list[Article]:
        """Fetches raw items, sanitizes them, and stores them in the database."""
        ...

class DigestService(Protocol):
    """
    Interface for compiling and formatting the twice-daily news digests.
    """
    async def compile_digest(self) -> Digest:
        """Runs the categorization, deduplication, ranking, and formatting rules."""
        ...

class TelegramService(Protocol):
    """
    Interface for communicating with the Telegram Bot API.
    """
    async def send_digest(self, digest: Digest) -> bool:
        """Sends the compiled digest to the configured Telegram channel."""
        ...
