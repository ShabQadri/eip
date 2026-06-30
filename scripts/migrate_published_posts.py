"""
Database migration script to refactor published_posts external ID storage.
"""
import sys
from pathlib import Path
import sqlite3
import json

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def run_migration():
    db_path = project_root / "data" / "sqlite" / "entertainment.db"
    if not db_path.exists():
        print("Database file does not exist. No migration needed.")
        return {
            "old_row_count": 0,
            "new_row_count": 0,
            "mismatched_rows": 0,
            "duplicate_rows": 0
        }

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Start transaction
        cursor.execute("BEGIN TRANSACTION")

        # 1. Fetch old table info
        cursor.execute("PRAGMA table_info(published_posts)")
        columns = [col[1] for col in cursor.fetchall()]

        if "telegram_message_id" not in columns and "external_post_id" not in columns:
            print("Table published_posts already migrated. Skipping.")
            conn.commit()
            conn.close()
            return {
                "old_row_count": 0,
                "new_row_count": 0,
                "mismatched_rows": 0,
                "duplicate_rows": 0
            }

        # 2. Get old table data dynamically checking column presence
        has_event_id = "event_id" in columns
        has_post_type = "post_type" in columns
        
        event_id_expr = "event_id" if has_event_id else "NULL"
        post_type_expr = "post_type" if has_post_type else "NULL"
        posted_at_col = "posted_at" if "posted_at" in columns else "published_at"
        
        cursor.execute(f"SELECT id, digest_id, {event_id_expr}, platform, {post_type_expr}, telegram_message_id, external_post_id, {posted_at_col}, created_at, updated_at FROM published_posts")
        old_rows = cursor.fetchall()
        old_row_count = len(old_rows)

        # 3. Create new table (published_posts_new)
        cursor.execute("""
            CREATE TABLE published_posts_new (
                id VARCHAR(36) NOT NULL, 
                digest_id VARCHAR(36), 
                event_id VARCHAR(36), 
                post_type VARCHAR(50), 
                platform VARCHAR(50) NOT NULL, 
                external_id VARCHAR(255), 
                metadata_json JSON NOT NULL, 
                published_at DATETIME NOT NULL, 
                created_at DATETIME, 
                updated_at DATETIME, 
                PRIMARY KEY (id), 
                FOREIGN KEY(digest_id) REFERENCES digests (id), 
                FOREIGN KEY(event_id) REFERENCES events (id),
                CONSTRAINT uq_publication_tracking UNIQUE (event_id, platform, post_type)
            )
        """)

        # 4. Copy and transform rows into new table
        duplicate_rows = 0
        inserted_keys = set()
        for row in old_rows:
            post_id, digest_id, event_id, platform, post_type, tg_msg_id, ext_post_id, pub_at, created_at, updated_at = row
            
            # Key for duplicate checking
            unique_key = (event_id, platform, post_type)
            if unique_key in inserted_keys:
                duplicate_rows += 1
                print(f"Warning: Duplicate row detected for event_id={event_id}, platform={platform}, post_type={post_type}. Skipping to satisfy unique constraint.")
                continue
            
            inserted_keys.add(unique_key)
            
            # Map external_id
            ext_id = tg_msg_id or ext_post_id or None
            
            # Map metadata_json
            meta = {}
            if platform == "TELEGRAM" and ext_id:
                meta["message_id"] = ext_id
            elif platform == "WEBSITE":
                meta["slug"] = ext_id or ""
            elif platform == "INSTAGRAM":
                meta["post_id"] = ext_id or ""
                meta["media_id"] = ""
                
            cursor.execute("""
                INSERT INTO published_posts_new (id, digest_id, event_id, platform, post_type, external_id, metadata_json, published_at, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (post_id, digest_id, event_id, platform, post_type, ext_id, json.dumps(meta), pub_at, created_at, updated_at))

        # 5. Validate row counts
        cursor.execute("SELECT COUNT(*) FROM published_posts_new")
        new_row_count = cursor.fetchone()[0]
        
        mismatched_rows = old_row_count - new_row_count - duplicate_rows

        if mismatched_rows != 0:
            raise ValueError(f"Migration mismatch! Old row count: {old_row_count}, New row count: {new_row_count}, Duplicates skipped: {duplicate_rows}")

        # 6. Rename tables
        cursor.execute("DROP TABLE published_posts")
        cursor.execute("ALTER TABLE published_posts_new RENAME TO published_posts")

        # 7. Re-create indexes
        cursor.execute("CREATE INDEX ix_published_posts_digest_id ON published_posts (digest_id)")
        cursor.execute("CREATE INDEX ix_published_posts_event_id ON published_posts (event_id)")
        cursor.execute("CREATE INDEX ix_published_posts_platform ON published_posts (platform)")
        cursor.execute("CREATE INDEX ix_published_posts_post_type ON published_posts (post_type)")
        cursor.execute("CREATE INDEX ix_published_posts_published_at ON published_posts (published_at)")

        cursor.execute("COMMIT")
        print("Migration transaction committed successfully.")
        
        return {
            "old_row_count": old_row_count,
            "new_row_count": new_row_count,
            "mismatched_rows": mismatched_rows,
            "duplicate_rows": duplicate_rows
        }

    except Exception as e:
        cursor.execute("ROLLBACK")
        print(f"Migration failed and transaction was rolled back: {e}")
        raise e
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
