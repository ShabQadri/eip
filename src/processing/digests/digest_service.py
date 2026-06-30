"""
Digest service orchestrator coordinating selection, formatting, and database storage.
"""

import logging
from typing import List, Optional
from sqlalchemy.orm import Session
from src.models.event import Event
from src.processing.digests.breaking_detector import BreakingDetector
from src.processing.digests.digest_selector import DigestSelector
from src.processing.digests.digest_formatter import DigestFormatter
from src.processing.digests.telegram_formatter import TelegramFormatter

logger = logging.getLogger("eip.digest_service")

class DigestService:
    """
    Main coordinator service for all digest operations.
    """
    def __init__(
        self,
        breaking_detector: BreakingDetector,
        digest_selector: DigestSelector,
        digest_formatter: DigestFormatter,
        telegram_formatter: TelegramFormatter
    ) -> None:
        self.breaking_detector = breaking_detector
        self.digest_selector = digest_selector
        self.digest_formatter = digest_formatter
        self.telegram_formatter = telegram_formatter

    def generate_digest(
        self,
        session: Session,
        digest_type: str = "morning",
        telegram_safe: bool = False
    ) -> str:
        """
        Generates morning/evening digests by coordinating existing components.
        """
        events = self.digest_selector.select_events_for_digest(session)
        try:
            from src.services.metrics_service import MetricsService
            MetricsService().record_metric(session, "average_digest_size", len(events))
        except Exception:
            pass

        digest_text = self.digest_formatter.format_digest(events, digest_type=digest_type)
        if telegram_safe:
            return self.telegram_formatter.format_digest_message(digest_text)
        return digest_text

    def get_breaking_events(
        self,
        session: Session
    ) -> List[Event]:
        """
        Queries recent events and filters them using BreakingDetector.
        """
        from datetime import datetime, timezone, timedelta
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=24)
        events = session.query(Event).filter(
            (Event.last_article_at == None) | (Event.last_article_at >= cutoff)
        ).all()
        
        return [evt for evt in events if self.breaking_detector.is_breaking(evt)]

    def process_new_events(self, db: Session, events: List[Event]) -> None:
        """
        Processes new events for breaking alerts and daily digests.
        """
        pass

    def generate_daily_digest(self, db: Session) -> Optional[str]:
        """
        Generates and stores the daily digest.
        """
        return self.generate_digest(db)

