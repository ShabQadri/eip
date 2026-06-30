"""
Feeds package for managing RSS feed ingestion, pre-filtering, and parsing.
"""

from src.feeds.rss_fetcher import RSSFetcher
from src.feeds.rss_parser import RSSParser
from src.feeds.editorial_filter import EditorialFilter
from src.feeds.importance_engine import ImportanceEngine
from src.feeds.collection_service import CollectionService, CollectionResult
