"""
Demonstration script for EIP Event Engine and Smart Deduplication.
"""

import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add project root to sys.path to enable absolute imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.database.base import Base
from src.models.source import Source
from src.models.article import Article
from src.models.event import Event
from src.processing.events.event_service import EventService

def run_demo() -> None:
    # 1. Initialize temporary SQLite Database
    engine = create_engine("sqlite://")
    Base.metadata.create_all(bind=engine)
    
    Session = sessionmaker(bind=engine)
    db = Session()

    print("--- Event Engine Demonstration ---")
    print("Initializing test database & seeding sources...")

    # Seed mock sources
    source_variety = Source(
        id="source-variety-123",
        name="Variety",
        domain="variety.com",
        rss_url="https://variety.com/feed/",
        source_type="RSS",
        source_tier=1,
        policy="SUMMARY_ALLOWED",
        enabled=True
    )
    source_deadline = Source(
        id="source-deadline-456",
        name="Deadline",
        domain="deadline.com",
        rss_url="https://deadline.com/feed/",
        source_type="RSS",
        source_tier=1,
        policy="SUMMARY_ALLOWED",
        enabled=True
    )
    db.add(source_variety)
    db.add(source_deadline)
    db.commit()

    # Create EventService
    service = EventService()

    # 2. Define the duplicate-like articles
    now = datetime.now(timezone.utc)
    articles_data = [
        {
            "source_id": "source-variety-123",
            "title": "Dune Messiah Begins Filming",
            "url": "https://variety.com/dune-messiah-filming",
            "description": "Cameras roll on Denis Villeneuve's third installment in Jordan.",
            "importance_score": 80,
            "category": "Movie",
            "published_at": now - timedelta(minutes=10),
            "hash": "hash-dune-1"
        },
        {
            "source_id": "source-deadline-456",
            "title": "Dune 3 Starts Production",
            "url": "https://deadline.com/dune-3-starts",
            "description": "The third part in the Dune franchise begins filming.",
            "importance_score": 85,
            "category": "Movie",
            "published_at": now - timedelta(minutes=5),
            "hash": "hash-dune-2"
        },
        {
            "source_id": "source-variety-123",
            "title": "Cameras Roll on Dune Messiah",
            "url": "https://variety.com/cameras-roll-dune",
            "description": "Official confirmation that Dune Messiah has entered production.",
            "importance_score": 90,
            "category": "Movie",
            "published_at": now,
            "hash": "hash-dune-3"
        }
    ]

    print("\nProcessing incoming articles:")
    for idx, art_dict in enumerate(articles_data, 1):
        art = Article(**art_dict)
        db.add(art)
        db.flush()

        print(f"  [{idx}] Processing: '{art.title}' (Source: {art_dict['source_id']}, Score: {art.importance_score})")
        matched_event = service.process_article(db, art)
        db.commit()
        print(f"      -> Linked to Event: '{matched_event.canonical_title}' (ID: {matched_event.id})")

    # 3. Retrieve results and verify aggregation
    events = db.query(Event).all()
    articles = db.query(Article).all()

    print("\n=================================")
    print("=== Execution Summary ===")
    print(f"Total Input Articles: {len(articles_data)}")
    print(f"Total Canonical Events Created: {len(events)}")
    print("=================================")

    if len(events) == 1:
        event = events[0]
        print(f"Event Canonical Title: {event.canonical_title}")
        print(f"Event Type:            {event.event_type}")
        print(f"Event Pattern:         {event.event_pattern}")
        print(f"Event Status:          {event.status}")
        print(f"Article Count:         {event.article_count}")
        print(f"Source Count:          {event.source_count}")
        print(f"Source Domains:        {event.source_domains_json}")
        print(f"Aliases List:          {event.aliases_json}")
        print(f"Event Importance:      {event.importance_score} (Formula: max(80,85,90) + 3*(2-1) = 93)")
        print("\nLinked Articles:")
        for idx, art in enumerate(event.articles, 1):
            print(f"  - Article {idx}: '{art.title}' [URL: {art.url}]")
    else:
        print(f"Warning: Expected exactly 1 event but found {len(events)} events!")

    db.close()

if __name__ == "__main__":
    run_demo()
