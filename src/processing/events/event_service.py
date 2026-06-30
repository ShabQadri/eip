"""
Event service orchestrating matching, building, and review consensus aggregation.
"""

import json
import re
from pathlib import Path
from typing import Optional, List
from sqlalchemy.orm import Session
from src.models.event import Event
from src.models.article import Article
from src.models.review_consensus import ReviewConsensus
from src.processing.events.title_cleaner import TitleCleaner
from src.processing.events.alias_manager import AliasManager
from src.processing.events.franchise_detector import FranchiseDetector
from src.processing.events.similarity_engine import SimilarityEngine
from src.processing.events.event_matcher import EventMatcher
from src.processing.events.event_builder import EventBuilder

class EventService:
    """
    Main service class to process accepted articles, link them to events, and aggregate reviews.
    """
    def __init__(
        self,
        ignore_titles_path: Optional[Path] = None
    ) -> None:
        self.title_cleaner = TitleCleaner()
        self.alias_manager = AliasManager()
        self.franchise_detector = FranchiseDetector()
        
        # Instantiate engines and matchers
        self.similarity_engine = SimilarityEngine(self.alias_manager)
        self.event_matcher = EventMatcher(self.similarity_engine, self.franchise_detector)
        self.event_builder = EventBuilder(self.alias_manager, self.franchise_detector, self.similarity_engine)

        if ignore_titles_path is None:
            project_root = Path(__file__).resolve().parent.parent.parent.parent
            ignore_titles_path = project_root / "data" / "events" / "ignore_titles.json"

        self.ignore_titles: List[str] = []
        if ignore_titles_path.exists():
            with open(ignore_titles_path, "r", encoding="utf-8") as f:
                self.ignore_titles = json.load(f)

    def _should_ignore_creation(self, title: str) -> bool:
        """Checks if a title contains any substrings that should prevent event creation."""
        t = (title or "").lower()
        return any(ignore.lower() in t for ignore in self.ignore_titles)

    def parse_review_score(self, text: str) -> Optional[int]:
        """
        Parses review scores out of text and converts them to base 100.
        - X/10 -> X * 10
        - X/5  -> X * 20
        - X%   -> X
        """
        if not text:
            return None

        # 1. Check for X/10 (e.g. 8/10, 8.5/10)
        match_10 = re.search(r"\b(\d+(?:\.\d+)?)\s*/\s*10\b", text)
        if match_10:
            try:
                val = float(match_10.group(1))
                if 0 <= val <= 10:
                    return int(val * 10)
            except ValueError:
                pass

        # 2. Check for X/5 (e.g. 4/5, 4.5/5)
        match_5 = re.search(r"\b(\d+(?:\.\d+)?)\s*/\s*5\b", text)
        if match_5:
            try:
                val = float(match_5.group(1))
                if 0 <= val <= 5:
                    return int(val * 20)
            except ValueError:
                pass

        # 3. Check for X% (e.g. 90%)
        match_pct = re.search(r"\b(\d+)\s*%", text)
        if match_pct:
            try:
                val = int(match_pct.group(1))
                if 0 <= val <= 100:
                    return val
            except ValueError:
                pass

        return None

    def _update_review_consensus(self, db: Session, event: Event, article: Article) -> None:
        """Helper to run rule-based review score extraction and aggregate ReviewConsensus."""
        # Check if the article represents a review
        is_review = (
            article.category == "Review" or 
            "review" in (article.title or "").lower() or 
            "rating" in (article.title or "").lower()
        )
        if not is_review:
            return

        # Fetch or create ReviewConsensus for this event
        consensus = db.query(ReviewConsensus).filter_by(event_id=event.id).first()
        if not consensus:
            consensus = ReviewConsensus(
                event_id=event.id,
                title=f"Consensus for {event.canonical_title}",
                review_count=0,
                review_source_count=0,
                review_articles_count=0,
                critic_score=None,
                sentiment=None
            )
            db.add(consensus)
            db.flush()

        # Update article domain and publish date logs
        consensus.review_articles_count += 1
        if article.published_at:
            if consensus.last_review_at is None or article.published_at > consensus.last_review_at:
                consensus.last_review_at = article.published_at

        # Extract all scores from review articles currently linked to this event
        linked_reviews = db.query(Article).filter(
            Article.event_id == event.id,
            (Article.category == "Review") | 
            (Article.title.like("%review%")) | 
            (Article.title.like("%rating%"))
        ).all()

        scores = []
        domains = set()
        for art in linked_reviews:
            # Get article domain
            if art.source:
                domains.add(art.source.domain)
            
            # Parse score
            full_text = f"{art.title} {art.description or ''}"
            score = self.parse_review_score(full_text)
            if score is not None:
                scores.append(score)

        consensus.review_source_count = len(domains)
        consensus.review_count = len(scores)

        if scores:
            avg_score = int(sum(scores) / len(scores))
            consensus.critic_score = avg_score

            # Sentiment boundaries
            if avg_score >= 70:
                consensus.sentiment = "POSITIVE"
            elif avg_score < 40:
                consensus.sentiment = "NEGATIVE"
            else:
                consensus.sentiment = "MIXED"
        else:
            consensus.critic_score = None
            consensus.sentiment = None

    def process_article(self, db: Session, article: Article) -> Optional[Event]:
        """
        Processes an accepted article:
        1. Search for matching event.
        2. If found, link article to the event and update metrics.
        3. If not found, check ignore list; if not ignored, create a new event.
        4. Triggers review consensus parser if article matches review patterns.
        """
        # Find matching event
        event = self.event_matcher.find_match(db, article)
        is_new = False

        if event:
            # Update existing event
            event = self.event_builder.update_event(db, event, article)
        else:
            # Check if this title is in the ignore list
            if self._should_ignore_creation(article.title):
                # Skipped - prevent creating generic events
                return None
            
            # Create new event
            event = self.event_builder.create_event(db, article)
            is_new = True

        # Trigger review consensus updates
        self._update_review_consensus(db, event, article)

        # Record metrics
        try:
            from src.services.metrics_service import MetricsService
            ms = MetricsService()
            if is_new:
                ms.increment(db, "events_created")
            else:
                ms.increment(db, "events_merged")
        except Exception:
            pass

        return event
