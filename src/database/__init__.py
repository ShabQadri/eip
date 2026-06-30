"""
Database package for managing SQLite connections and migrations.
Conforms to startup requirements by deferring database initialization and connection execution.
"""

import sqlite3
from pathlib import Path

class DatabaseManager:
    """
    Manages SQLite lifecycle and connection retrieval.
    """
    def __init__(self, db_path: str) -> None:
        """
        Initializes the DatabaseManager.
        Expects a sqlite:/// URI or direct file path.
        """
        # Parse URI if present, otherwise treat as file path
        if db_path.startswith("sqlite:///"):
            clean_path = db_path.replace("sqlite:///", "")
        else:
            clean_path = db_path
            
        self.db_path = Path(clean_path)

    def get_connection(self) -> sqlite3.Connection:
        """
        Establishes and returns a new connection.
        Enables Write-Ahead Logging (WAL) for optimized concurrency on Oracle Free Tier.
        """
        # Ensure target directories exist before connecting
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # Optimize SQLite for performance
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        
        return conn

    def initialize_schema(self) -> None:
        """
        Creates necessary tables for RSS items and digests.
        To be run explicitly during installation or application setup.
        """
        # Setup tables (Stubs for future implementation)
        pass
