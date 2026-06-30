"""
Database engine configuration and SQLite optimization pragmas.
Defers actual file creation until active connections are opened.
"""

from sqlite3 import Connection as SQLite3Connection
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker
from src.config.settings import settings

# Create engine instance (lazy creation, doesn't open connections on import)
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}
)

# Bind session maker
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

@event.listens_for(Engine, "connect")
def set_sqlite_pragmas(dbapi_connection, connection_record) -> None:
    """
    Sets optimized SQLite settings when connection is opened.
    Enforces Foreign Keys, WAL mode, synchronous=NORMAL, and busy timeouts.
    """
    if isinstance(dbapi_connection, SQLite3Connection):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON;")
        cursor.execute("PRAGMA journal_mode = WAL;")
        cursor.execute("PRAGMA synchronous = NORMAL;")
        cursor.execute("PRAGMA busy_timeout = 5000;")
        cursor.close()
