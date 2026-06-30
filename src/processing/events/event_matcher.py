"""
Event matcher comparing incoming articles against existing database events.
"""

from typing import Optional
from sqlalchemy.orm import Session
from src.models.event import Event
from src.models.article import Article
from src.processing.events.similarity_engine import SimilarityEngine
from src.processing.events.franchise_detector import FranchiseDetector

class EventMatcher:
    """
    Finds a matching database event for an incoming article.
    """
    def __init__(
        self, 
        similarity_engine: SimilarityEngine,
        franchise_detector: FranchiseDetector
    ) -> None:
        self.similarity_engine = similarity_engine
        self.franchise_detector = franchise_detector

    def find_match(self, db: Session, article: Article) -> Optional[Event]:
        """
        Scans existing events in the database to find a match for the article.
        Returns the highest-scoring Event if similarity >= 85, else None.
        """
        # Determine franchise and pattern of the incoming article
        art_franchise, _ = self.franchise_detector.detect(
            article.title, 
            article.description
        )
        art_pattern = self.similarity_engine.detect_pattern(
            article.title,
            article.description
        )
        art_season, art_year = self.similarity_engine.extract_season_and_year(
            article.title,
            article.description
        )

        events = db.query(Event).all()
        best_event: Optional[Event] = None
        best_score = 0.0

        for event in events:
            # Skip if season number or event year conflict (only for renewals/season announcements)
            is_tv_lifecycle = (
                art_pattern in ["RENEWAL", "SEASON_ANNOUNCEMENT"] or
                event.event_pattern in ["RENEWAL", "SEASON_ANNOUNCEMENT"]
            )
            if is_tv_lifecycle:
                if art_season is not None and event.season_number is not None and art_season != event.season_number:
                    continue
                if art_year is not None and event.event_year is not None and art_year != event.event_year:
                    continue
            # We compare the article title to the event canonical title
            # and any of its aliases
            scores = []
            
            # 1. Compare with canonical title
            s_canonical = self.similarity_engine.calculate_similarity(
                title1=article.title,
                title2=event.canonical_title,
                desc1=article.description or "",
                desc2=event.summary or "",
                franchise1=art_franchise,
                franchise2=event.franchise,
                pattern1=art_pattern,
                pattern2=event.event_pattern
            )
            scores.append(s_canonical)

            # 2. Compare with all aliases stored in aliases_json
            aliases = event.aliases_json or []
            for alias in aliases:
                s_alias = self.similarity_engine.calculate_similarity(
                    title1=article.title,
                    title2=alias,
                    desc1=article.description or "",
                    desc2=event.summary or "",
                    franchise1=art_franchise,
                    franchise2=event.franchise,
                    pattern1=art_pattern,
                    pattern2=event.event_pattern
                )
                scores.append(s_alias)

            max_event_score = max(scores) if scores else 0.0

            if max_event_score >= 85.0 and max_event_score > best_score:
                best_score = max_event_score
                best_event = event

        return best_event
