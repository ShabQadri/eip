"""
Event builder responsible for creating and updating event records in the database.
"""

from datetime import datetime, timezone
from typing import Optional, List
from sqlalchemy.orm import Session
from src.models.event import Event
from src.models.article import Article
from src.models.source import Source
from src.processing.events.alias_manager import AliasManager
from src.processing.events.franchise_detector import FranchiseDetector
from src.processing.events.similarity_engine import SimilarityEngine

class EventBuilder:
    """
    Handles event creation and updates based on incoming articles.
    """
    def __init__(
        self,
        alias_manager: AliasManager,
        franchise_detector: FranchiseDetector,
        similarity_engine: SimilarityEngine
    ) -> None:
        self.alias_manager = alias_manager
        self.franchise_detector = franchise_detector
        self.similarity_engine = similarity_engine

    def _get_source_domain(self, db: Session, article: Article) -> str:
        """Helper to get the source domain for an article."""
        if article.source:
            return article.source.domain or "unknown.com"
        # Fallback to query
        source = db.query(Source).filter_by(id=article.source_id).first()
        if source:
            return source.domain or "unknown.com"
        return "unknown.com"

    def _determine_status(self, text: str, current_status: Optional[str] = None) -> Optional[str]:
        """Determines the event status based on keywords."""
        t = text.lower()
        if any(kw in t for kw in ["begins filming", "starts production", "cameras roll", "enters production"]):
            return "IN_PRODUCTION"
        elif any(kw in t for kw in ["release date", "premiere date", "streaming date"]):
            return "RELEASED"
        elif any(kw in t for kw in ["cancelled", "cancellation"]):
            return "CANCELLED"
        return current_status or "ANNOUNCED"

    def _to_naive_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        """Converts an offset-aware datetime to offset-naive UTC datetime."""
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def generate_display_title(self, canonical_title: str, event_pattern: Optional[str]) -> str:
        """
        Generates an editorial-friendly display title for the event based on its pattern.
        """
        if not event_pattern:
            return canonical_title

        mapping = {
            "PRODUCTION_START": f"{canonical_title} Begins Production",
            "TRAILER": f"{canonical_title} Releases Trailer",
            "RELEASE_DATE": f"{canonical_title} Sets Release Date",
            "RENEWAL": f"{canonical_title} Renewed",
            "CASTING": f"{canonical_title} Announces Casting",
            "AWARDS": f"{canonical_title} Wins Award",
        }
        return mapping.get(event_pattern, canonical_title)

    def create_event(self, db: Session, article: Article) -> Event:
        """Creates a new Event from an article."""
        # Detect franchise and region
        franchise, region = self.franchise_detector.detect(article.title, article.description)
        if not region:
            region = article.region or "GLOBAL"

        # Determine canonical title
        core_title = self.similarity_engine.extract_core_title(article.title)
        canonical_title = self.alias_manager.get_canonical_title(core_title)
        if not canonical_title:
            if franchise and franchise.lower() in core_title.lower():
                canonical_title = franchise
            else:
                canonical_title = core_title.title() if core_title else article.title

        # Determine event pattern
        event_pattern = self.similarity_engine.detect_pattern(article.title, article.description)

        # Extract season number and event year
        season_number, event_year = self.similarity_engine.extract_season_and_year(article.title, article.description)

        # Apply final event model cleanup rules to prevent unnecessary fragmentation
        is_tv_lifecycle = (
            event_pattern in ["RENEWAL", "SEASON_ANNOUNCEMENT"] or
            (article.category == "TV Series" and event_pattern is not None)
        )
        if not is_tv_lifecycle:
            season_number = None

        if event_pattern in ["TRAILER", "PRODUCTION_START", "RELEASE_DATE", "CASTING", "AWARDS"] or event_pattern is None:
            event_year = None

        # Determine status
        status = self._determine_status(f"{article.title} {article.description or ''}")

        # Generate display title
        display_title = self.generate_display_title(canonical_title, event_pattern)

        # Domain tracking
        domain = self._get_source_domain(db, article)

        # Aliases list: if article title is different from canonical title, add it as alias
        aliases = []
        if article.title.lower().strip() != canonical_title.lower().strip():
            aliases.append(article.title)

        pub_at = self._to_naive_utc(article.published_at or datetime.now(timezone.utc))

        event = Event(
            canonical_title=canonical_title,
            display_title=display_title,
            event_type=article.category or "General",
            importance_score=article.importance_score or 0,
            summary=article.description or article.title,
            region=region,
            franchise=franchise,
            status=status,
            source_count=1,
            article_count=1,
            first_article_at=pub_at,
            last_article_at=pub_at,
            aliases_json=aliases,
            source_domains_json=[domain],
            event_pattern=event_pattern,
            season_number=season_number,
            event_year=event_year,
            first_reported_at=pub_at,
            last_updated_at=pub_at,
            tmdb_id=None,
            event_history_json=[{
                "action": "create",
                "timestamp": pub_at.isoformat(),
                "article_id": article.id,
                "title": article.title,
                "source": domain
            }]
        )

        db.add(event)
        # Flush to generate ID
        db.flush()
        
        # Link article
        article.event_id = event.id
        return event

    def update_event(self, db: Session, event: Event, article: Article) -> Event:
        """Links an article to an existing event and updates event counters, status, and scores."""
        # Link article
        article.event_id = event.id

        # Update article count
        event.article_count += 1

        # Update timestamps
        pub_at = self._to_naive_utc(article.published_at or datetime.now(timezone.utc))
        evt_first = self._to_naive_utc(event.first_article_at)
        evt_last = self._to_naive_utc(event.last_article_at)

        if evt_first is None or pub_at < evt_first:
            event.first_article_at = pub_at
            event.first_reported_at = pub_at
        if evt_last is None or pub_at > evt_last:
            event.last_article_at = pub_at
            event.last_updated_at = pub_at

        # Update domain tracking
        domain = self._get_source_domain(db, article)
        domains = list(event.source_domains_json or [])
        if domain not in domains:
            domains.append(domain)
            event.source_domains_json = domains
        event.source_count = len(domains)

        # Update aliases list
        aliases = list(event.aliases_json or [])
        clean_art_title = article.title.strip()
        if (clean_art_title.lower() != event.canonical_title.lower() and 
            clean_art_title not in aliases):
            aliases.append(clean_art_title)
            event.aliases_json = aliases

        # Update event history
        history = list(event.event_history_json or [])
        history.append({
            "action": "update",
            "timestamp": pub_at.isoformat(),
            "article_id": article.id,
            "title": article.title,
            "source": domain,
            "relationship": getattr(article, "event_relationship", None)
        })
        event.event_history_json = history

        # Update status
        full_text = f"{article.title} {article.description or ''}"
        event.status = self._determine_status(full_text, event.status)

        # Update pattern if empty
        if not event.event_pattern:
            event.event_pattern = self.similarity_engine.detect_pattern(article.title, article.description)

        # Update display title if empty or if pattern is now populated/changed
        if not event.display_title or (event.event_pattern and event.display_title == event.canonical_title):
            event.display_title = self.generate_display_title(event.canonical_title, event.event_pattern)

        # Update season and year if empty, following final cleanup rules
        if event.season_number is None or event.event_year is None:
            s_num, yr = self.similarity_engine.extract_season_and_year(article.title, article.description)
            is_tv_lifecycle = (
                event.event_pattern in ["RENEWAL", "SEASON_ANNOUNCEMENT"] or
                (event.event_type == "TV Series" and event.event_pattern is not None)
            )
            if is_tv_lifecycle and event.season_number is None and s_num is not None:
                event.season_number = s_num
            if event.event_pattern not in ["TRAILER", "PRODUCTION_START", "RELEASE_DATE", "CASTING", "AWARDS"] and event.event_pattern is not None:
                if event.event_year is None and yr is not None:
                    event.event_year = yr

        # Update importance score using formula:
        # event_importance = max(article.importance_score) + 3 * (source_count - 1) capped at 100
        # Include current article and all other linked articles
        scores = [article.importance_score or 0]
        # Query existing linked article scores
        existing_scores = db.query(Article.importance_score).filter(
            Article.event_id == event.id, 
            Article.id != article.id
        ).all()
        for row in existing_scores:
            if row[0] is not None:
                scores.append(row[0])

        max_art_score = max(scores) if scores else 0
        bonus = 3 * (event.source_count - 1)
        event.importance_score = min(100, max_art_score + bonus)

        return event
