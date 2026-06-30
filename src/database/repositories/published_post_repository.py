"""
PublishedPost repository.
"""

from typing import Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.published_post import PublishedPost
from src.database.repositories import BaseRepository

class PublishedPostRepository(BaseRepository[PublishedPost]):
    """
    CRUD repository for PublishedPost entity.
    """
    def __init__(self) -> None:
        super().__init__(PublishedPost)

    def get_by_digest_id(self, db: Session, digest_id: str) -> Sequence[PublishedPost]:
        """Retrieves publication records associated with a specific digest."""
        statement = select(PublishedPost).where(
            PublishedPost.digest_id == digest_id
        )
        return db.scalars(statement).all()
