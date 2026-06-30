"""
Collection service orchestrating feed registry, fetching, parsing, pre-filtering, 
editorial filtering, importance scoring, and database commits.
"""

import time
import json
import logging
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import aiohttp
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models import Source, Article
from src.database.repositories.source_repository import SourceRepository
from src.database.repositories.article_repository import ArticleRepository
from src.database.repositories.settings_repository import SettingsRepository

from src.feeds.rss_fetcher import RSSFetcher
from src.feeds.rss_parser import RSSParser
from src.feeds.article_normalizer import ArticleNormalizer
from src.feeds.editorial_filter import EditorialFilter
from src.feeds.importance_engine import ImportanceEngine
from src.feeds.feed_registry import FeedRegistry

logger = logging.getLogger("eip.collection_service")

@dataclass
class CollectionResult:
    """
    Summary stats detailing the outcome of a feed collection sweep.
    """
    feeds_processed: int = 0
    feeds_succeeded: int = 0
    feeds_failed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    articles_fetched: int = 0
    articles_pre_filtered: int = 0
    articles_rejected: int = 0
    articles_stored: int = 0
    articles_skipped_by_cache: int = 0
    rejected_gossip: int = 0
    rejected_low_value: int = 0
    rejected_duplicates: int = 0
    duration_seconds: float = 0.0


class CollectionService:
    """
    Orchestrates the ingestion, validation, and storage pipeline for feed articles.
    """
    def __init__(self) -> None:
        self.fetcher = RSSFetcher()
        self.normalizer = ArticleNormalizer()

        project_root = Path(__file__).resolve().parent.parent.parent
        editorial_rules_path = project_root / "data" / "feeds" / "editorial_rules.json"

        with open(editorial_rules_path, "r", encoding="utf-8") as f:
            rules = json.load(f)

        blacklist = rules.get("blacklist_keywords", [])
        self.parser = RSSParser(blacklist_keywords=blacklist)
        self.filter = EditorialFilter()
        self.importance_engine = ImportanceEngine()

        self.source_repo = SourceRepository()
        self.article_repo = ArticleRepository()
        self.settings_repo = SettingsRepository()

        # Load disabled feeds list
        disabled_path = project_root / "data" / "feeds" / "disabled_feeds.json"
        self.disabled_urls = set()
        if disabled_path.exists():
            try:
                with open(disabled_path, "r", encoding="utf-8") as f:
                    self.disabled_urls = set(json.load(f))
            except Exception as e:
                logger.error(f"Error loading disabled feeds: {e}")

        # Map feed url to region
        self.url_to_region = {}
        registry = FeedRegistry()
        for item in registry.load_configured_sources():
            self.url_to_region[item.get("rss_url")] = item.get("region", "GLOBAL")

    async def collect_all(self, db: Session, dry_run: bool = False) -> CollectionResult:
        """
        Runs a complete collection Sweep over all enabled sources.
        """
        start_time = time.time()
        result = CollectionResult()

        # Retrieve active sources from database
        sources = self.source_repo.get_all(db, limit=100)
        active_sources = [
            s for s in sources 
            if s.enabled and s.rss_url not in self.disabled_urls
        ]

        # Retrieve threshold settings
        settings = self.settings_repo.get_latest(db)
        threshold = settings.digest_threshold if settings else 60

        # TCP Connection pool optimized for Oracle Free Tier (10 max concurrent)
        conn = aiohttp.TCPConnector(limit=10)
        async with aiohttp.ClientSession(connector=conn) as session:
            for source in active_sources:
                result.feeds_processed += 1
                url = source.rss_url
                if not url:
                    result.feeds_failed += 1
                    continue

                # Circuit breaker pre-check (database-driven)
                is_broken = False
                if source.consecutive_failures >= 3 and source.last_failed_fetch:
                    time_elapsed = datetime.now(timezone.utc).replace(tzinfo=None) - source.last_failed_fetch
                    if time_elapsed < timedelta(hours=6):
                        is_broken = True

                if is_broken:
                    result.articles_skipped_by_cache += 1
                    result.feeds_failed += 1
                    continue

                # Async fetch
                xml_content, status = await self.fetcher.fetch(session, url)

                if status == "304_NOT_MODIFIED":
                    result.cache_hits += 1
                    result.feeds_succeeded += 1
                    if not dry_run:
                        source.last_successful_fetch = datetime.now(timezone.utc).replace(tzinfo=None)
                        source.consecutive_failures = 0
                        db.commit()
                    continue

                if xml_content is None:
                    # Generic fetch failure
                    result.feeds_failed += 1
                    if not dry_run:
                        source.last_failed_fetch = datetime.now(timezone.utc).replace(tzinfo=None)
                        source.consecutive_failures += 1
                        
                        if source.consecutive_failures >= 5:
                            source.enabled = False
                            source.disabled_reason = "5 consecutive failures"
                            source.disabled_at = datetime.now(timezone.utc).replace(tzinfo=None)
                            
                            logger.warning(
                                f"Disabled feed:\n{source.name}\nReason:\n5 consecutive failures."
                            )
                            
                            try:
                                from src.services.metrics_service import MetricsService
                                MetricsService().increment(db, "dead_feeds_detected", source="CollectionService")
                            except Exception as me:
                                logger.error(f"Failed to record dead_feeds_detected metric: {me}")
                                
                        db.commit()
                    continue

                # Success path
                result.cache_misses += 1
                result.feeds_succeeded += 1
                if not dry_run:
                    source.last_successful_fetch = datetime.now(timezone.utc).replace(tzinfo=None)
                    source.consecutive_failures = 0
                    db.commit()

                # Parse feed
                parsed_entries, pre_filtered = self.parser.parse_feed_entries(xml_content)
                result.articles_fetched += len(parsed_entries) + pre_filtered
                result.articles_pre_filtered += pre_filtered

                for parsed in parsed_entries:
                    region = self.url_to_region.get(source.rss_url, "GLOBAL")
                    article_model = self.normalizer.normalize_to_model(
                        parsed, source.id, region
                    )

                    # Editorial Filter
                    is_approved, reason = self.filter.evaluate_article(article_model)
                    if not is_approved:
                        result.articles_rejected += 1
                        if reason == "GOSSIP":
                            result.rejected_gossip += 1
                        else:
                            result.rejected_low_value += 1
                        continue

                    # Importance Scoring & Category assignment
                    self.importance_engine.score_article(article_model)

                    # Reject if below configured threshold
                    if article_model.importance_score < threshold:
                        result.articles_rejected += 1
                        result.rejected_low_value += 1
                        continue

                    # Check for duplicates using unique hash
                    existing = self.article_repo.get_by_hash(db, article_model.hash)
                    if existing:
                        result.rejected_duplicates += 1
                        continue

                    # Store in database
                    if not dry_run:
                        try:
                            self.article_repo.create(db, article_model)
                            db.commit()
                            result.articles_stored += 1
                        except IntegrityError:
                            db.rollback()
                            result.rejected_duplicates += 1
                    else:
                        result.articles_stored += 1

        result.duration_seconds = round(time.time() - start_time, 2)
        if not dry_run:
            try:
                from src.services.metrics_service import MetricsService
                ms = MetricsService()
                ms.increment(db, "feeds_processed", result.feeds_processed)
                ms.increment(db, "feeds_succeeded", result.feeds_succeeded)
                ms.increment(db, "feeds_failed", result.feeds_failed)
                ms.increment(db, "articles_fetched", result.articles_fetched)
                ms.increment(db, "articles_rejected", result.articles_rejected)
                ms.increment(db, "articles_stored", result.articles_stored)
            except Exception as e:
                logger.error(f"Failed to record collection metrics: {e}")
        return result
