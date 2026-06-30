"""
RSS Parser utilizing feedparser to extract, sanitize, and pre-filter news items.
"""

import re
import html
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional
import feedparser
from src.constants.regex_patterns import HTML_TAG_CLEANSER

class RSSParser:
    """
    Parses raw XML feed documents, extracts structured data, and filters out obvious gossip early.
    """
    def __init__(self, blacklist_keywords: List[str]) -> None:
        self.blacklist_keywords = [kw.lower() for kw in blacklist_keywords]

    def clean_text(self, text: str) -> str:
        """Unescapes HTML entities, strips HTML tags, and collapses spaces."""
        if not text:
            return ""
        # Decode HTML entities (e.g. &amp; -> &)
        text = html.unescape(text)
        # Remove HTML tags using defined regex cleanser
        text = HTML_TAG_CLEANSER.sub("", text)
        # Collapse multiple spacing/newlines
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def pre_filter_entry(self, entry: Dict[str, Any]) -> bool:
        """
        Scans raw title only for rapid early rejection of gossip/clickbait.
        """
        title = (entry.get("title") or "").lower()

        for keyword in self.blacklist_keywords:
            if keyword in title:
                return True
        return False

    def parse_feed_entries(self, xml_content: str) -> Tuple[List[Dict[str, Any]], int]:
        """
        Parses XML content and extracts clean records.
        Returns:
            Tuple[List[cleaned_articles_dicts], count_of_pre_filtered_items]
        """
        feed = feedparser.parse(xml_content)
        cleaned_entries: List[Dict[str, Any]] = []
        pre_filtered_count = 0

        for entry in feed.entries:
            # 1. Early pre-filter check
            if self.pre_filter_entry(entry):
                pre_filtered_count += 1
                continue

            # 2. Extract and clean text elements
            title = self.clean_text(entry.get("title", ""))
            url = entry.get("link", "")
            
            raw_desc = entry.get("summary") or entry.get("description") or ""
            description = self.clean_text(raw_desc)
            
            # Truncate description length to 300 characters
            if len(description) > 300:
                description = description[:297] + "..."

            author = self.clean_text(entry.get("author", ""))
            author = author if author else None

            # Parse datetime tuple (feedparser parses formats into struct_time)
            published_at: Optional[datetime] = None
            for date_key in ("published_parsed", "updated_parsed", "created_parsed"):
                time_struct = entry.get(date_key)
                if time_struct:
                    try:
                        published_at = datetime(*time_struct[:6])
                        break
                    except Exception:
                        pass

            cleaned_entries.append({
                "title": title,
                "url": url,
                "description": description,
                "author": author,
                "published_at": published_at
            })

        return cleaned_entries, pre_filtered_count
