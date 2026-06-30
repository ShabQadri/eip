"""
Integration tests for the EventService and ReviewConsensus aggregation rules.
"""

import tempfile
import os
import json
from pathlib import Path
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import Base
from src.models.event import Event
from src.models.article import Article
from src.models.source import Source
from src.models.review_consensus import ReviewConsensus
from src.processing.events.event_service import EventService

def test_event_service_processing() -> None:
    # 1. Setup DB
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    db = Session()

    # 2. Setup mock ignore list JSON
    ignore_list = ["live updates", "recap"]
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode="w", encoding="utf-8") as tmp_i:
        json.dump(ignore_list, tmp_i)
        tmp_i_path = Path(tmp_i.name)

    try:
        service = EventService(ignore_titles_path=tmp_i_path)

        # Seed source records
        src1 = Source(id="src-1", name="Variety", domain="variety.com", rss_url="url1", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
        src2 = Source(id="src-2", name="Deadline", domain="deadline.com", rss_url="url2", source_type="RSS", source_tier=1, policy="SUMMARY_ALLOWED")
        db.add(src1)
        db.add(src2)
        db.commit()

        # A. Process typical article
        art1 = Article(
            source_id="src-1",
            title="Dune Messiah Begins Filming",
            description="The third Dune movie enters production.",
            importance_score=80,
            category="Movie",
            published_at=datetime.now(timezone.utc),
            hash="h1",
            url="url1"
        )
        db.add(art1)
        db.flush()

        event1 = service.process_article(db, art1)
        assert event1 is not None
        assert event1.canonical_title == "Dune Messiah"
        assert event1.status == "IN_PRODUCTION"
        assert event1.article_count == 1
        assert event1.source_count == 1
        assert event1.source_domains_json == ["variety.com"]
        assert event1.importance_score == 80

        # B. Link duplicate article from different source with higher score
        art2 = Article(
            source_id="src-2",
            title="Dune 3 Starts Production",
            description="Production starts on Dune Part Three.",
            importance_score=90,
            category="Movie",
            published_at=datetime.now(timezone.utc),
            hash="h2",
            url="url2"
        )
        db.add(art2)
        db.flush()

        event2 = service.process_article(db, art2)
        assert event2.id == event1.id
        assert event2.article_count == 2
        assert event2.source_count == 2
        assert "deadline.com" in event2.source_domains_json
        # Importance: max(80, 90) + 3*(2-1) = 93
        assert event2.importance_score == 93

        # C. Ignore list title check (prevent event creation)
        art_ignored = Article(
            source_id="src-1",
            title="Weekend report and live updates",
            description="Ignore me.",
            importance_score=10,
            category="Industry News",
            published_at=datetime.now(timezone.utc),
            hash="h-ignored",
            url="url3"
        )
        db.add(art_ignored)
        db.flush()

        ignored_event = service.process_article(db, art_ignored)
        assert ignored_event is None

        # D. Review Consensus parsing
        # Link a review article
        art_rev = Article(
            source_id="src-1",
            title="Dune Messiah Review - A Masterpiece (9/10)",
            description="Our review rating is 90% for this cinema milestone.",
            importance_score=80,
            category="Review",
            published_at=datetime.now(timezone.utc),
            hash="h-rev",
            url="url-rev"
        )
        db.add(art_rev)
        db.flush()

        service.process_article(db, art_rev)
        
        # Verify ReviewConsensus
        consensus = db.query(ReviewConsensus).filter_by(event_id=event1.id).first()
        assert consensus is not None
        assert consensus.review_articles_count == 1
        assert consensus.review_count == 1  # found 9/10
        assert consensus.critic_score == 90
        assert consensus.sentiment == "POSITIVE"

    finally:
        db.close()
        os.remove(tmp_i_path)
