"""
ReviewConsensus repository.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.review_consensus import ReviewConsensus
from src.database.repositories import BaseRepository

class ReviewConsensusRepository(BaseRepository[ReviewConsensus]):
    """
    CRUD repository for ReviewConsensus entity.
    """
    def __init__(self) -> None:
        super().__init__(ReviewConsensus)

    def get_by_event_id(self, db: Session, event_id: str) -> Optional[ReviewConsensus]:
        """Retrieves consensus ratings linked to a specific event ID."""
        statement = select(ReviewConsensus).where(
            ReviewConsensus.event_id == event_id
        )
        return db.scalars(statement).first()
