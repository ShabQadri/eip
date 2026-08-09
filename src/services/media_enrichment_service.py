import os
import re
import json
import logging
import urllib.parse
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import aiohttp
from rapidfuzz import fuzz

from src.config.settings import settings

logger = logging.getLogger("eip.media_enrichment")

class MediaEnrichmentService:
    """
    Enriches entertainment events with official artwork from TMDB and trailers from YouTube.
    """
    def __init__(self, tmdb_key: Optional[str] = None, youtube_key: Optional[str] = None) -> None:
        self.tmdb_key = tmdb_key or settings.TMDB_API_KEY
        self.youtube_key = youtube_key or settings.YOUTUBE_API_KEY
        
        project_root = Path(__file__).resolve().parent.parent.parent
        self.official_channels_path = project_root / "data" / "media" / "official_channels.json"
        self.tmdb_cache_path = project_root / "data" / "cache" / "tmdb_cache.json"
        self.youtube_cache_path = project_root / "data" / "cache" / "youtube_cache.json"
        
        self._load_official_channels()
        self._load_caches()

    def _load_official_channels(self) -> None:
        self.official_channels = {}
        if self.official_channels_path.exists():
            try:
                with open(self.official_channels_path, "r", encoding="utf-8") as f:
                    self.official_channels = json.load(f)
            except Exception as e:
                logger.error(f"Error loading official channels config: {e}")

    def _load_caches(self) -> None:
        self.tmdb_cache = {}
        if self.tmdb_cache_path.exists():
            try:
                with open(self.tmdb_cache_path, "r", encoding="utf-8") as f:
                    self.tmdb_cache = json.load(f)
            except Exception as e:
                logger.error(f"Error loading TMDB cache: {e}")
                
        self.youtube_cache = {}
        if self.youtube_cache_path.exists():
            try:
                with open(self.youtube_cache_path, "r", encoding="utf-8") as f:
                    self.youtube_cache = json.load(f)
            except Exception as e:
                logger.error(f"Error loading YouTube cache: {e}")

    def _save_tmdb_cache(self) -> None:
        try:
            self.tmdb_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tmdb_cache_path, "w", encoding="utf-8") as f:
                json.dump(self.tmdb_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving TMDB cache: {e}")

    def _save_youtube_cache(self) -> None:
        try:
            self.youtube_cache_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.youtube_cache_path, "w", encoding="utf-8") as f:
                json.dump(self.youtube_cache, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving YouTube cache: {e}")

    async def search_tmdb(self, title: str, media_type: str = "movie", year: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Queries TMDB for a movie or TV show, validates the results, and caches outcomes.
        """
        if not self.tmdb_key:
            logger.warning("TMDB API key not configured. Skipping TMDB enrichment.")
            return None

        # Check Cache
        cache_key = f"{media_type}:{title}:{year or ''}"
        if cache_key in self.tmdb_cache:
            return self.tmdb_cache[cache_key]

        query = urllib.parse.quote(title)
        
        # Decide endpoint
        tmdb_type = "movie" if media_type.lower() in ["movie", "cinema"] else "tv"
        url = f"https://api.themoviedb.org/3/search/{tmdb_type}?api_key={self.tmdb_key}&query={query}"
        
        if year:
            if tmdb_type == "movie":
                url += f"&year={year}"
            else:
                url += f"&first_air_date_year={year}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    # Increment metrics
                    self._increment_metric("media_lookup_requests")
                    if response.status == 200:
                        data = await response.json()
                        results = data.get("results", [])
                        if not results:
                            # Try again without year as a fallback
                            if year:
                                fallback_url = f"https://api.themoviedb.org/3/search/{tmdb_type}?api_key={self.tmdb_key}&query={query}"
                                async with session.get(fallback_url, timeout=10) as fb_response:
                                    if fb_response.status == 200:
                                        fb_data = await fb_response.json()
                                        results = fb_data.get("results", [])

                        # Validate results
                        for res in results:
                            res_title = res.get("title") or res.get("name") or ""
                            res_date = res.get("release_date") or res.get("first_air_date") or ""
                            
                            # Calculate name similarity
                            sim = fuzz.token_sort_ratio(title.lower(), res_title.lower())
                            if sim >= 80:
                                # Validate year if date is present
                                if year and res_date:
                                    try:
                                        res_year = int(res_date.split("-")[0])
                                        # Allow release slip +/- 1 year
                                        if abs(res_year - year) > 1:
                                            continue
                                    except ValueError:
                                        pass
                                
                                # Matched! Extract metadata
                                matched_data = {
                                    "tmdb_id": str(res.get("id")),
                                    "title": res_title,
                                    "poster_url": f"https://image.tmdb.org/t/p/w500{res.get('poster_path')}" if res.get("poster_path") else None,
                                    "backdrop_url": f"https://image.tmdb.org/t/p/w1280{res.get('backdrop_path')}" if res.get("backdrop_path") else None
                                }
                                self.tmdb_cache[cache_key] = matched_data
                                self._save_tmdb_cache()
                                return matched_data
                                
                        # No valid matches
                        self.tmdb_cache[cache_key] = None
                        self._save_tmdb_cache()
                        return None
                    else:
                        self._increment_metric("media_lookup_failures")
                        logger.error(f"TMDB search failed with HTTP {response.status}")
                        return None
        except Exception as e:
            self._increment_metric("media_lookup_failures")
            logger.error(f"Error querying TMDB API: {e}")
            return None

    async def search_official_youtube_trailer(self, entity_name: str, year: Optional[int] = None) -> Optional[str]:
        """
        Queries YouTube for verified official trailer and returns video URL.
        """
        if not self.youtube_key:
            logger.warning("YouTube API key not configured. Skipping YouTube trailer lookup.")
            return None

        # Check Cache
        cache_key = f"{entity_name}:{year or ''}"
        if cache_key in self.youtube_cache:
            return self.youtube_cache[cache_key]

        # Build clean search query
        query_str = f"{entity_name} "
        if year:
            query_str += f"{year} "
        query_str += "official trailer"
        
        query = urllib.parse.quote(query_str)
        url = f"https://www.googleapis.com/youtube/v3/search?part=snippet&q={query}&type=video&maxResults=5&key={self.youtube_key}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    self._increment_metric("media_lookup_requests")
                    if response.status == 200:
                        data = await response.json()
                        items = data.get("items", [])
                        
                        # Load whitelist channels mapping
                        whitelist_channel_ids = {ch["channel_id"].lower() for ch in self.official_channels.values() if "channel_id" in ch}
                        whitelist_channel_titles = {ch["channel_title"].lower() for ch in self.official_channels.values() if "channel_title" in ch}

                        bad_keywords = ["fanmade", "fan-made", "concept", "teaser edit", "reaction", "review", "recap", "compilation", "edit", "spoiler"]

                        for item in items:
                            snippet = item.get("snippet", {})
                            video_title = snippet.get("title", "")
                            channel_id = snippet.get("channelId", "")
                            channel_title = snippet.get("channelTitle", "")
                            video_id = item.get("id", {}).get("videoId")

                            if not video_id:
                                continue

                            # 1. Reject fan edits/reactions
                            video_title_lower = video_title.lower()
                            if any(kw in video_title_lower for kw in bad_keywords):
                                continue

                            # 2. Strong match check (video title must contain movie name keywords)
                            # Collapse punctuation and spaces for comparison
                            clean_entity = re.sub(r"[^\w\s]", "", entity_name.lower())
                            words = clean_entity.split()
                            # Check if at least 70% of entity keywords are present in the video title
                            matches = sum(1 for w in words if w in video_title_lower)
                            if matches < max(1, len(words) * 0.7):
                                continue

                            # 3. Channel verification
                            is_official = (
                                channel_id.lower() in whitelist_channel_ids or
                                channel_title.lower() in whitelist_channel_titles or
                                "official" in channel_title.lower() or
                                any(studio in channel_title.lower() for studio in ["netflix", "marvel", "disney", "warner bros", "paramount", "sony", "universal", "hbo", "prime video"])
                            )

                            if is_official:
                                trailer_url = f"https://www.youtube.com/watch?v={video_id}"
                                self.youtube_cache[cache_key] = trailer_url
                                self._save_youtube_cache()
                                self._increment_metric("media_trailers_found")
                                return trailer_url

                        # No official match found
                        self.youtube_cache[cache_key] = None
                        self._save_youtube_cache()
                        return None
                    else:
                        self._increment_metric("media_lookup_failures")
                        logger.error(f"YouTube search failed with HTTP {response.status}")
                        return None
        except Exception as e:
            self._increment_metric("media_lookup_failures")
            logger.error(f"Error querying YouTube API: {e}")
            return None

    def _increment_metric(self, name: str) -> None:
        """Saves metric increment directly to database."""
        try:
            from src.database.database import SessionLocal
            from src.services.metrics_service import MetricsService
            db = SessionLocal()
            try:
                MetricsService().increment(db, name, source="MediaEnrichmentService")
                db.commit()
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to record media metrics: {e}")
