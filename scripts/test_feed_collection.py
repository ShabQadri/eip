"""
Test feed collection script for executing feed sweep and printing statistics.
"""

import sys
import argparse
import asyncio
from pathlib import Path

# Add project root to sys.path to enable absolute imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database.database import SessionLocal
from src.feeds.collection_service import CollectionService

async def main() -> None:
    """Parses command line arguments and triggers collection sweep."""
    parser = argparse.ArgumentParser(description="Entertainment Intelligence Platform Feed Ingestion Tool")
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Fetch, parse, and filter without saving to SQLite"
    )
    args = parser.parse_args()

    db = SessionLocal()
    service = CollectionService()

    print("Starting feed collection Sweep...")
    if args.dry_run:
        print("[DRY-RUN MODE ACTIVE - Database inserts will be simulated]")

    try:
        result = await service.collect_all(db, dry_run=args.dry_run)

        # Print statistics exactly as requested
        print("\n=== Ingestion Statistics ===")
        print(f"Feeds Processed: {result.feeds_processed}")
        print(f"Feeds Succeeded: {result.feeds_succeeded}")
        print(f"Feeds Failed: {result.feeds_failed}")
        print(f"Cache Hits: {result.cache_hits}")
        print(f"Cache Misses: {result.cache_misses}")
        print(f"Articles Fetched: {result.articles_fetched}")
        print(f"Articles Pre-Filtered: {result.articles_pre_filtered}")
        print(f"Articles Rejected: {result.articles_rejected}")
        print(f"Articles Stored: {result.articles_stored}")
        print(f"Articles Skipped by Cache: {result.articles_skipped_by_cache}")
        print(f"\nGossip Rejected: {result.rejected_gossip}")
        print(f"Low Value Rejected: {result.rejected_low_value}")
        print(f"Duplicates: {result.rejected_duplicates}")
        print(f"Duration: {result.duration_seconds} seconds")
        print("============================")

    except Exception as e:
        print(f"Fatal error during ingestion sweep: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(main())
