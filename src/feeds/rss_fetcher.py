"""
Asynchronous RSS feed fetcher with ETag/Last-Modified caching and a circuit breaker.
"""

import os
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import aiohttp

logger = logging.getLogger("eip.rss_fetcher")

class FeedCache:
    """
    Manages loading, retrieving, and committing ETag/modified cache state.
    """
    def __init__(self, cache_path: Path) -> None:
        self.cache_path = cache_path
        self.cache: Dict[str, Any] = {}
        self.load()

    def load(self) -> None:
        """Loads cached states from the file system."""
        if self.cache_path.exists():
            try:
                with open(self.cache_path, "r", encoding="utf-8") as f:
                    self.cache = json.load(f)
            except Exception as e:
                logger.error(f"Error loading feed cache file: {e}")
                self.cache = {}
        else:
            self.cache = {}

    def save(self) -> None:
        """Saves current state to the cache file."""
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_path, "w", encoding="utf-8") as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving feed cache file: {e}")

    def get_entry(self, url: str) -> Dict[str, Any]:
        """Gets cache details for a feed URL. Returns defaults if absent."""
        return self.cache.get(url, {
            "etag": "",
            "last_modified": "",
            "last_success": "",
            "last_error": "",
            "consecutive_failures": 0
        })

    def update_entry(self, url: str, updates: Dict[str, Any]) -> None:
        """Modifies cache record for a feed and triggers file saving."""
        entry = self.get_entry(url)
        entry.update(updates)
        self.cache[url] = entry
        self.save()


class RSSFetcher:
    """
    Handles asynchronous HTTP requests for RSS feeds with cache matching and circuit breakers.
    """
    def __init__(self, timeout_seconds: int = 15) -> None:
        project_root = Path(__file__).resolve().parent.parent.parent
        self.cache_path = project_root / "data" / "cache" / "feed_cache.json"
        self.cache_manager = FeedCache(self.cache_path)
        self.timeout = timeout_seconds
        self.user_agent = "Entertainment Intelligence Platform Ingester/1.0"

    def is_circuit_broken(self, url: str) -> bool:
        """
        Determines if a feed fetch should be skipped due to excessive consecutive failures.
        Active circuit breakers block requests for 6 hours.
        """
        entry = self.cache_manager.get_entry(url)
        consecutive_failures = entry.get("consecutive_failures", 0)
        
        if consecutive_failures >= 3:
            last_err_str = entry.get("last_error", "")
            if last_err_str:
                try:
                    # Parse timestamp (handles Z or +00:00 format implicitly in Python 3.11+)
                    clean_ts = last_err_str.replace("Z", "+00:00")
                    last_error = datetime.fromisoformat(clean_ts)
                    time_elapsed = datetime.now(timezone.utc) - last_error
                    if time_elapsed < timedelta(hours=6):
                        return True
                except ValueError:
                    pass
        return False

    async def fetch(self, session: aiohttp.ClientSession, url: str) -> Tuple[Optional[str], str]:
        """
        Requests XML content from a feed asynchronously.
        Returns:
            Tuple[xml_content_or_none, status_string_reason]
        """
        # 1. Circuit Breaker Check
        if self.is_circuit_broken(url):
            logger.warning(f"Circuit breaker active for {url} - skipping fetch.")
            return None, "CIRCUIT_BROKEN"

        entry = self.cache_manager.get_entry(url)
        headers = {
            "User-Agent": self.user_agent
        }
        
        # Apply caching headers if present
        if entry.get("etag"):
            headers["If-None-Match"] = entry["etag"]
        if entry.get("last_modified"):
            headers["If-Modified-Since"] = entry["last_modified"]

        try:
            timeout_cfg = aiohttp.ClientTimeout(total=self.timeout)
            async with session.get(url, headers=headers, timeout=timeout_cfg) as response:
                if response.status == 304:
                    # Cache hit, file hasn't changed
                    self.cache_manager.update_entry(url, {
                        "last_success": datetime.now(timezone.utc).isoformat(),
                        "consecutive_failures": 0
                    })
                    return None, "304_NOT_MODIFIED"
                
                if response.status == 200:
                    xml_content = await response.text()
                    # Capture ETag / Last-Modified caching properties
                    etag = response.headers.get("ETag", "")
                    last_mod = response.headers.get("Last-Modified", "")
                    self.cache_manager.update_entry(url, {
                        "etag": etag,
                        "last_modified": last_mod,
                        "last_success": datetime.now(timezone.utc).isoformat(),
                        "consecutive_failures": 0
                    })
                    return xml_content, "200_OK"
                
                # Non-200/304 status codes
                status_reason = f"HTTP_{response.status}"
                self.record_failure(url, status_reason)
                return None, status_reason

        except Exception as e:
            err_reason = type(e).__name__
            logger.error(f"Failed to fetch RSS feed {url}: {e}")
            self.record_failure(url, err_reason)
            return None, err_reason

    def record_failure(self, url: str, reason: str) -> None:
        """Increments failure logs in the cache state."""
        entry = self.cache_manager.get_entry(url)
        failures = entry.get("consecutive_failures", 0) + 1
        self.cache_manager.update_entry(url, {
            "last_error": datetime.now(timezone.utc).isoformat(),
            "consecutive_failures": failures
        })
