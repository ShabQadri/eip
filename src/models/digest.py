"""
Digest entity model.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base
from src.models.mixins import TimestampMixin

class Digest(Base, TimestampMixin):
    """
    Represents a compiled digest to be sent across channels.
    """
    __tablename__ = "digests"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    
    # Allowed: MORNING, EVENING, BREAKING, WEEKLY
    digest_type: Mapped[str] = mapped_column(
        String(50), 
        index=True, 
        nullable=False
    )
    content: Mapped[str] = mapped_column(String(8000), nullable=False)
    image_path: Mapped[Optional[str]] = mapped_column(
        String(512), 
        nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        index=True, 
        nullable=True
    )

    # Relationships
    published_posts: Mapped[List["PublishedPost"]] = relationship(
        "PublishedPost", 
        back_populates="digest", 
        cascade="all, delete-orphan"
    )
