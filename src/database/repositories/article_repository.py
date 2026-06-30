"""
Article repository.
"""

from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.article import Article
from src.database.repositories import BaseRepository

class ArticleRepository(BaseRepository[Article]):
    """
    CRUD repository for Article entity.
    """
    def __init__(self) -> None:
        super().__init__(Article)

    def get_by_url(self, db: Session, url: str) -> Optional[Article]:
        """Retrieves an article by its unique URL."""
        statement = select(Article).where(Article.url == url)
        return db.scalars(statement).first()

    def get_by_hash(self, db: Session, article_hash: str) -> Optional[Article]:
        """Retrieves an article by its unique hash."""
        statement = select(Article).where(Article.hash == article_hash)
        return db.scalars(statement).first()

    def get_by_event_id(self, db: Session, event_id: str) -> Sequence[Article]:
        """Retrieves all articles linked to a specific canonical event."""
        statement = select(Article).where(Article.event_id == event_id)
        return db.scalars(statement).all()
