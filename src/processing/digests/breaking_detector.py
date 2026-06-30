"""
Breaking detector module to identify high-importance events that qualify for breaking alerts.
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional
from src.models.event import Event

logger = logging.getLogger("eip.breaking_detector")

class BreakingDetector:
    """
    Identifies if a given event qualifies as a breaking news event based on importance threshold,
    source confirmation counts, age, and type/pattern exclusion rules.
    """
    def __init__(self, breaking_threshold: int = 80) -> None:
        self.breaking_threshold = breaking_threshold

    def should_ignore_pattern(self, pattern: Optional[str]) -> bool:
        """
        Determines if an event pattern or type should be excluded from breaking alerts.
        """
        if not pattern:
            return False
        return pattern.upper() in {"REVIEWS", "BOX_OFFICE_DAILY", "GALLERY", "PHOTO"}

    def is_breaking(self, event: Event, reference_time: Optional[datetime] = None) -> bool:
        """
        Determines whether the given event is breaking.
        Returns True or False only.
        """
        # 1. Event importance must be >= breaking_threshold
        if event.importance_score < self.breaking_threshold:
            return False

        # 2. Event must be confirmed by multiple sources
        if event.source_count < 2:
            return False

        # 3. Ignore ignored patterns or event types
        if self.should_ignore_pattern(event.event_pattern) or self.should_ignore_pattern(event.event_type):
            return False

        # 4. Ignore events older than 24 hours
        if event.last_article_at:
            ref = reference_time or datetime.now(timezone.utc)
            # Ensure naive comparison matching database timestamp timezone format (naive UTC)
            if ref.tzinfo is not None:
                ref = ref.astimezone(timezone.utc).replace(tzinfo=None)
            
            age = ref - event.last_article_at
            if age > timedelta(hours=24):
                return False

        return True
