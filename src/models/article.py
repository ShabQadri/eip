"""
Article entity model.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base
from src.models.mixins import TimestampMixin

class Article(Base, TimestampMixin):
    """
    Represents an ingested entertainment news article.
    """
    __tablename__ = "articles"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    source_id: Mapped[str] = mapped_column(
        String(36), 
        ForeignKey("sources.id"), 
        index=True, 
        nullable=False
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("events.id"), 
        index=True, 
        nullable=True
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    url: Mapped[str] = mapped_column(
        String(1024), 
        unique=True, 
        index=True, 
        nullable=False
    )
    description: Mapped[Optional[str]] = mapped_column(
        String(4000), 
        nullable=True
    )
    author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        index=True, 
        nullable=True
    )
    hash: Mapped[str] = mapped_column(
        String(64), 
        unique=True, 
        index=True, 
        nullable=False
    )
    category: Mapped[Optional[str]] = mapped_column(
        String(100), 
        index=True, 
        nullable=True
    )
    importance_score: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        index=True, 
        nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(String(4000), nullable=True)
    
    # Allowed: HOLLYWOOD, INDIA, PAN_INDIA, KOREA, ANIME, GLOBAL
    region: Mapped[Optional[str]] = mapped_column(
        String(50), 
        index=True, 
        nullable=True
    )
    
    is_gossip: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        index=True, 
        nullable=False
    )
    is_verified: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    
    # E.g. "new", "processed", "ignored"
    status: Mapped[str] = mapped_column(
        String(50), 
        default="new", 
        index=True, 
        nullable=False
    )

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="articles")
    event: Mapped[Optional["Event"]] = relationship(
        "Event", 
        back_populates="articles"
    )
