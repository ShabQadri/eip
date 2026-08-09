import os
import sys
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

# Add project root to sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.database.database import SessionLocal

def get_db_path() -> Path:
    # Resolve the database path from settings or directly from file
    db_path = project_root / "data" / "sqlite" / "entertainment.db"
    return db_path

def check_integrity(conn: sqlite3.Connection) -> bool:
    cursor = conn.cursor()
    cursor.execute("PRAGMA integrity_check")
    result = cursor.fetchone()[0]
    return result == "ok"

def get_table_columns(conn: sqlite3.Connection, table_name: str) -> list[str]:
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]

def run_migration():
    db_path = get_db_path()
    if not db_path.exists():
        print(f"Database file {db_path} does not exist. Initialize it first using scripts/init_db.py.")
        sys.exit(1)

    print(f"Opening database: {db_path}")
    conn = sqlite3.connect(db_path)
    
    # 1. Verify source database integrity
    if not check_integrity(conn):
        print("Source database integrity check failed. Aborting migration.")
        conn.close()
        sys.exit(1)
    print("Source database integrity check: OK")

    # 2. Create backup folder and backup database
    backup_dir = project_root / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = backup_dir / f"eip-pre-ai-migration-{timestamp}.db"
    
    print(f"Backing up database to: {backup_path}")
    shutil.copy(db_path, backup_path)
    
    # 3. Verify backup integrity
    if not backup_path.exists() or backup_path.stat().st_size == 0:
        print("Backup file is empty or does not exist. Aborting migration.")
        conn.close()
        sys.exit(1)
        
    backup_conn = sqlite3.connect(backup_path)
    if not check_integrity(backup_conn):
        print("Backup database integrity check failed. Aborting migration.")
        backup_conn.close()
        conn.close()
        sys.exit(1)
    backup_conn.close()
    print("Backup database integrity check: OK")

    # 4. Migrate Schema
    cursor = conn.cursor()
    
    # Missing Article columns
    article_new_columns = {
        "full_text": "TEXT",
        "content_hash": "VARCHAR(64)",
        "canonical_url": "VARCHAR(1024)",
        "published_source_url": "VARCHAR(1024)",
        "article_published_at": "DATETIME",
        "content_extracted_at": "DATETIME",
        "content_extraction_status": "VARCHAR(50)",
        "og_image_url": "VARCHAR(1024)",
        "media_json": "JSON",
        "video_urls_json": "JSON",
        "event_relationship": "VARCHAR(50)",
        "ai_analysis_json": "JSON"
    }

    # Missing Event columns
    event_new_columns = {
        "first_reported_at": "DATETIME",
        "last_updated_at": "DATETIME",
        "tmdb_id": "VARCHAR(50)",
        "event_history_json": "JSON"
    }

    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # Ingress missing columns to articles
        existing_articles_cols = get_table_columns(conn, "articles")
        for col_name, col_type in article_new_columns.items():
            if col_name not in existing_articles_cols:
                print(f"Adding column articles.{col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE articles ADD COLUMN {col_name} {col_type}")
            else:
                print(f"Column articles.{col_name} already exists. Skipping.")

        # Ingress missing columns to events
        existing_events_cols = get_table_columns(conn, "events")
        for col_name, col_type in event_new_columns.items():
            if col_name not in existing_events_cols:
                print(f"Adding column events.{col_name} ({col_type})")
                cursor.execute(f"ALTER TABLE events ADD COLUMN {col_name} {col_type}")
            else:
                print(f"Column events.{col_name} already exists. Skipping.")

        # Create indexes
        print("Creating indexes...")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_articles_content_hash ON articles (content_hash)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_events_tmdb_id ON events (tmdb_id)")
        
        # Verify row counts match (non-destructive check)
        cursor.execute("SELECT COUNT(*) FROM articles")
        art_count_before = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events")
        evt_count_before = cursor.fetchone()[0]

        cursor.execute("COMMIT")
        print("Migration transaction committed successfully.")
        
        # Verify database post-migration integrity
        if not check_integrity(conn):
            print("Integrity check failed post-migration!")
            sys.exit(1)
        print("Post-migration database integrity check: OK")

        # Verify row counts post migration
        cursor.execute("SELECT COUNT(*) FROM articles")
        art_count_after = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events")
        evt_count_after = cursor.fetchone()[0]
        
        assert art_count_before == art_count_after, "Articles row count mismatched after migration!"
        assert evt_count_before == evt_count_after, "Events row count mismatched after migration!"
        print(f"Row count validation: articles={art_count_after}, events={evt_count_after} (MATCH)")

    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"Migration transaction failed and was rolled back: {e}")
        conn.close()
        sys.exit(1)
        
    conn.close()
    print("Migration finished successfully.")

if __name__ == "__main__":
    run_migration()
