"""
Source repository.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.source import Source
from src.database.repositories import BaseRepository

class SourceRepository(BaseRepository[Source]):
    """
    CRUD repository for Source entity.
    """
    def __init__(self) -> None:
        super().__init__(Source)

    def get_by_domain(self, db: Session, domain: str) -> Optional[Source]:
        """Retrieves a source by its domain name."""
        statement = select(Source).where(Source.domain == domain)
        return db.scalars(statement).first()
