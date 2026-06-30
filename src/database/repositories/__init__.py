"""
Repository pattern abstractions for the Database CRUD operations.
"""

from typing import TypeVar, Generic, Type, Optional, Sequence
from sqlalchemy import select
from sqlalchemy.orm import Session
from src.database.base import Base

ModelType = TypeVar("ModelType", bound=Base)

class BaseRepository(Generic[ModelType]):
    """
    Base Repository class providing standard CRUD operations.
    """
    def __init__(self, model: Type[ModelType]) -> None:
        self.model = model

    def get_by_id(self, db: Session, id: str) -> Optional[ModelType]:
        """Retrieves a single record by its UUID."""
        return db.get(self.model, id)

    def get_all(self, db: Session, skip: int = 0, limit: int = 100) -> Sequence[ModelType]:
        """Retrieves a page of records."""
        statement = select(self.model).offset(skip).limit(limit)
        return db.scalars(statement).all()

    def create(self, db: Session, obj: ModelType) -> ModelType:
        """Adds a new object to the database session."""
        db.add(obj)
        db.flush()
        return obj

    def update(self, db: Session, db_obj: ModelType, update_data: dict) -> ModelType:
        """Applies modifications to an existing record."""
        for field, value in update_data.items():
            if hasattr(db_obj, field):
                setattr(db_obj, field, value)
        db.flush()
        return db_obj

    def delete(self, db: Session, id: str) -> bool:
        """Deletes a record by its UUID."""
        obj = self.get_by_id(db, id)
        if obj:
            db.delete(obj)
            db.flush()
            return True
        return False
