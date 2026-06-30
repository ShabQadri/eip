"""
Database initializer script.
Creates tables, indexes, and inserts the default settings record.
"""

import sys
from pathlib import Path

# Add project root to sys.path to enable absolute imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database.database import engine, SessionLocal
from src.database.base import Base

# Import all models to ensure they are registered on the Base metadata
from src.models.source import Source
from src.models.event import Event
from src.models.article import Article
from src.models.review_consensus import ReviewConsensus
from src.models.digest import Digest
from src.models.published_post import PublishedPost
from src.models.settings import Settings
from src.models.system_metric import SystemMetric

def init_db() -> None:
    """Creates SQLite database, all tables, and populates initial settings."""
    # Ensure the parent directory for the database exists
    db_path = project_root / "data" / "sqlite" / "entertainment.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)

    # Bind metadata and create all tables (including indexes defined on them)
    Base.metadata.create_all(bind=engine)

    # Insert default row into settings
    db = SessionLocal()
    try:
        settings_count = db.query(Settings).count()
        if settings_count == 0:
            default_config = Settings(
                article_retention_days=90,
                image_retention_days=180,
                log_retention_days=30,
                breaking_threshold=80,
                digest_threshold=60,
                max_articles_per_digest=12,
                cleanup_hour=2,
                keep_images=True,
                metric_retention_days=365
            )
            db.add(default_config)
            db.commit()
    except Exception as e:
        db.rollback()
        print(f"Error seeding database: {e}")
        sys.exit(1)
    finally:
        db.close()

    print("Database initialized successfully.")

if __name__ == "__main__":
    init_db()
