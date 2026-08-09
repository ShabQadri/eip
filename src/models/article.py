"""
Article entity model.
"""

import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
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

    # New AI and Article Reading Fields
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), index=True, nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    published_source_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    article_published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    content_extracted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    content_extraction_status: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    og_image_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    media_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    video_urls_json: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    event_relationship: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    ai_analysis_json: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    source: Mapped["Source"] = relationship("Source", back_populates="articles")
    event: Mapped[Optional["Event"]] = relationship(
        "Event", 
        back_populates="articles"
    )
