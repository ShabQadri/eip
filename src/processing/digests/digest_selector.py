"""
Digest selector module to filter and gather events that should be included in a digest.
"""

import logging
from typing import List, Optional, Any
from sqlalchemy.orm import Session
from src.models.event import Event
from src.models.settings import Settings

logger = logging.getLogger("eip.digest_selector")

class DigestSelector:
    """
    Selects events from the database that meet criteria for digest inclusion.
    """
    def __init__(
        self,
        digest_threshold: int = 60,
        max_articles: int = 12,
        publication_service: Optional[Any] = None
    ) -> None:
        self.digest_threshold = digest_threshold
        self.max_articles = max_articles
        if publication_service is None:
            from src.services.publication_service import PublicationService
            self.publication_service = PublicationService()
        else:
            self.publication_service = publication_service

    def get_digest_threshold(self, session: Session) -> int:
        """
        Reads digest threshold from system settings or falls back to default.
        """
        settings = session.query(Settings).first()
        if settings is not None:
            return settings.digest_threshold
        return self.digest_threshold

    def get_max_digest_size(self, session: Session) -> int:
        """
        Reads maximum articles per digest from system settings or falls back to default.
        """
        settings = session.query(Settings).first()
        if settings is not None:
            return settings.max_articles_per_digest
        return self.max_articles

    def is_event_published(self, session: Session, event_id: str) -> bool:
        """
        Checks if an event is already marked as published in published_posts.
        """
        for platform in ["TELEGRAM", "INSTAGRAM", "WEBSITE"]:
            for post_type in ["DIGEST_MORNING", "DIGEST_EVENING", "BREAKING_ALERT", "TELEGRAM", "INSTAGRAM", "WEBSITE"]:
                if self.publication_service.is_published(session, event_id, platform, post_type):
                    return True
        return False

    def select_events_for_digest(
        self,
        session: Session,
        limit: Optional[int] = None
    ) -> List[Event]:
        """
        Selects the most important unpublished events for digests.
        Ordered by importance DESC, then last_article_at DESC.
        """
        threshold = self.get_digest_threshold(session)
        max_size = self.get_max_digest_size(session)
        
        actual_limit = limit if limit is not None else max_size
        
        query = session.query(Event).filter(Event.importance_score >= threshold)
        query = query.order_by(
            Event.importance_score.desc(),
            Event.last_article_at.desc()
        )
        
        candidates = query.all()
        filtered = []
        for evt in candidates:
            if not self.is_event_published(session, evt.id):
                filtered.append(evt)
                if len(filtered) == actual_limit:
                    break
        return filtered

