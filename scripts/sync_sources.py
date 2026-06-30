"""
Sync script to manually populate/synchronize feed sources configuration into SQLite database.
"""

import sys
import json
from pathlib import Path
from urllib.parse import urlparse

# Add project root to sys.path to enable absolute imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database.database import SessionLocal
from src.database.repositories.source_repository import SourceRepository
from src.models import Source, Article, Event, ReviewConsensus, Digest, PublishedPost, Settings
from src.feeds.feed_registry import FeedRegistry

def sync_sources() -> None:
    """Reads data/feeds/feed_sources.json and synchronizes the sources DB table."""
    registry = FeedRegistry()
    configured_sources = registry.load_configured_sources()

    db = SessionLocal()
    source_repo = SourceRepository()

    created_count = 0
    updated_count = 0

    try:
        # Load source rules for policy mappings
        rules_path = project_root / "data" / "feeds" / "source_rules.json"
        source_rules = {}
        if rules_path.exists():
            with open(rules_path, "r", encoding="utf-8") as f:
                source_rules = json.load(f)

        for item in configured_sources:
            url = item.get("rss_url", "")
            
            # Extract domain from rss_url if not provided
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            if domain.startswith("www."):
                domain = domain[4:]

            policy = source_rules.get(domain, "SUMMARY_ALLOWED")

            # Check if source exists in database (by rss_url first, then domain)
            existing = db.query(Source).filter(Source.rss_url == url).first()
            if not existing:
                existing = source_repo.get_by_domain(db, domain)

            if existing:
                # Update attributes
                existing.name = item.get("name", existing.name)
                existing.source_tier = item.get("source_tier", existing.source_tier)
                existing.enabled = item.get("enabled", existing.enabled)
                existing.policy = policy
                existing.domain = domain
                updated_count += 1
            else:
                # Insert new source
                new_source = Source(
                    name=item.get("name", "Unknown Source"),
                    domain=domain,
                    rss_url=url,
                    source_type="RSS",
                    source_tier=item.get("source_tier", 3),
                    policy=policy,
                    enabled=item.get("enabled", True)
                )
                source_repo.create(db, new_source)
                created_count += 1

        db.commit()
        print(f"Synchronization complete: Created {created_count}, Updated {updated_count} sources.")
    except Exception as e:
        db.rollback()
        print(f"Error during synchronization: {e}")
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    sync_sources()
