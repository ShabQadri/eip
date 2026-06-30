"""
Settings repository.
"""

from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.models.settings import Settings
from src.database.repositories import BaseRepository

class SettingsRepository(BaseRepository[Settings]):
    """
    CRUD repository for Settings entity.
    """
    def __init__(self) -> None:
        super().__init__(Settings)

    def get_latest(self, db: Session) -> Optional[Settings]:
        """Retrieves the active settings row (ordered by creation)."""
        statement = select(Settings).order_by(Settings.created_at.desc())
        return db.scalars(statement).first()
