"""
Database session context managers.
"""

from contextlib import contextmanager
from typing import Generator
from sqlalchemy.orm import Session
from src.database.database import SessionLocal

@contextmanager
def db_session() -> Generator[Session, None, None]:
    """
    Yields a transactional database session context.
    Automatically commits transactions or performs rollbacks on exceptions.
    """
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
