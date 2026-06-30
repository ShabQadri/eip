"""
Source entity model.
"""

import uuid
from datetime import datetime
from typing import List, Optional
from sqlalchemy import String, Integer, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base
from src.models.mixins import TimestampMixin

class Source(Base, TimestampMixin):
    """
    Represents a feed or publication source.
    """
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=False
    )
    rss_url: Mapped[str | None] = mapped_column(
        String(512), 
        unique=True, 
        nullable=True
    )
    
    # Allowed: RSS, YOUTUBE, OFFICIAL, API, MANUAL
    source_type: Mapped[str] = mapped_column(
        String(50), 
        index=True, 
        nullable=False
    )
    
    # Tier: 1-3
    source_tier: Mapped[int] = mapped_column(
        Integer, 
        index=True, 
        nullable=False
    )
    
    # Allowed: HEADLINE_ONLY, SUMMARY_ALLOWED, BLOCKED
    policy: Mapped[str] = mapped_column(String(50), nullable=False)
    
    enabled: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        index=True, 
        nullable=False
    )
    trust_score: Mapped[int] = mapped_column(
        Integer, 
        default=100, 
        nullable=False
    )

    # Health tracking fields for collection services
    last_successful_fetch: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True
    )
    last_failed_fetch: Mapped[Optional[datetime]] = mapped_column(
        DateTime, 
        nullable=True
    )
    consecutive_failures: Mapped[int] = mapped_column(
        Integer, 
        default=0, 
        nullable=False
    )
    disabled_reason: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    disabled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True
    )

    # Relationships
    articles: Mapped[List["Article"]] = relationship(
        "Article", 
        back_populates="source", 
        cascade="all, delete-orphan"
    )
