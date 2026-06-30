"""
Event repository.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.event import Event
from src.database.repositories import BaseRepository

class EventRepository(BaseRepository[Event]):
    """
    CRUD repository for Event entity.
    """
    def __init__(self) -> None:
        super().__init__(Event)

    def get_by_title_and_region(self, db: Session, title: str, region: str) -> Optional[Event]:
        """Retrieves an event by its composite unique fields: title and region."""
        statement = select(Event).where(
            Event.canonical_title == title, 
            Event.region == region
        )
        return db.scalars(statement).first()
