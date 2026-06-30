"""
ReviewConsensus entity model.
"""

import uuid
from typing import Optional
from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base
from src.models.mixins import TimestampMixin

class ReviewConsensus(Base, TimestampMixin):
    """
    Aggregates critic and audience reviews for an event.
    """
    __tablename__ = "review_consensus"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("events.id"), 
        index=True, 
        nullable=True
    )
    title: Mapped[str] = mapped_column(
        String(255), 
        index=True, 
        nullable=False
    )
    critic_score: Mapped[Optional[int]] = mapped_column(
        Integer, 
        index=True, 
        nullable=True
    )
    audience_score: Mapped[Optional[int]] = mapped_column(
        Integer, 
        nullable=True
    )
    consensus_summary: Mapped[Optional[str]] = mapped_column(
        String(2000), 
        nullable=True
    )
    review_count: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )
    review_source_count: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )
    
    # Allowed: POSITIVE, MIXED, NEGATIVE
    sentiment: Mapped[Optional[str]] = mapped_column(
        String(50), 
        index=True, 
        nullable=True
    )

    review_articles_count: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )
    last_review_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True
    )

    # Relationships
    event: Mapped[Optional["Event"]] = relationship(
        "Event", 
        back_populates="review_consensus"
    )
