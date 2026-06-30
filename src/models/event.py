"""
Event entity model.
"""

import uuid
from typing import List, Optional
from datetime import datetime
from sqlalchemy import String, Integer, Boolean, UniqueConstraint, DateTime, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base
from src.models.mixins import TimestampMixin

class Event(Base, TimestampMixin):
    """
    Represents a canonical entertainment news event.
    """
    __tablename__ = "events"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    canonical_title: Mapped[str] = mapped_column(
        String(255), 
        index=True, 
        nullable=False
    )
    display_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False
    )
    event_type: Mapped[str] = mapped_column(
        String(100), 
        index=True, 
        nullable=False
    )
    importance_score: Mapped[int] = mapped_column(
        Integer, 
        index=True, 
        default=0, 
        nullable=False
    )
    summary: Mapped[Optional[str]] = mapped_column(String(2000), nullable=True)
    
    # Allowed: HOLLYWOOD, INDIA, PAN_INDIA, KOREA, ANIME, GLOBAL
    region: Mapped[Optional[str]] = mapped_column(
        String(50), 
        index=True, 
        nullable=True
    )
    franchise: Mapped[Optional[str]] = mapped_column(
        String(255), 
        index=True, 
        nullable=True
    )
    
    # Allowed: ANNOUNCED, IN_PRODUCTION, RELEASED, CANCELLED, COMPLETED
    status: Mapped[Optional[str]] = mapped_column(
        String(50), 
        index=True, 
        nullable=True
    )
    
    is_gossip: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )
    is_featured: Mapped[bool] = mapped_column(
        Boolean, 
        default=False, 
        nullable=False
    )

    # Event Deduplication & Engine Fields
    source_count: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        index=True, 
        nullable=False
    )
    article_count: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )
    first_article_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True
    )
    last_article_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        index=True, 
        nullable=True
    )
    aliases_json: Mapped[list] = mapped_column(
        JSON, 
        default=list, 
        nullable=False
    )
    source_domains_json: Mapped[list] = mapped_column(
        JSON, 
        default=list, 
        nullable=False
    )
    event_pattern: Mapped[Optional[str]] = mapped_column(
        String(100), 
        index=True, 
        nullable=True
    )
    season_number: Mapped[Optional[int]] = mapped_column(
        Integer,
        index=True,
        nullable=True
    )
    event_year: Mapped[Optional[int]] = mapped_column(
        Integer,
        index=True,
        nullable=True
    )
    # TODO: remove after migration.
    published: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
        index=True
    )

    __table_args__ = (
        UniqueConstraint(
            "canonical_title", 
            "region", 
            "event_pattern",
            "season_number",
            "event_year",
            name="uq_event_uniqueness"
        ),
    )

    # Relationships
    articles: Mapped[List["Article"]] = relationship(
        "Article", 
        back_populates="event"
    )
    review_consensus: Mapped[Optional["ReviewConsensus"]] = relationship(
        "ReviewConsensus", 
        back_populates="event", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
    published_posts: Mapped[List["PublishedPost"]] = relationship(
        "PublishedPost",
        back_populates="event",
        cascade="all, delete-orphan"
    )

    def __init__(self, **kwargs):
        if "display_title" not in kwargs and "canonical_title" in kwargs:
            kwargs["display_title"] = kwargs["canonical_title"]
        super().__init__(**kwargs)
