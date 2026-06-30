"""
PublishedPost entity model.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, DateTime, ForeignKey, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.database.base import Base
from src.models.mixins import TimestampMixin

class PublishedPost(Base, TimestampMixin):
    """
    Tracks digest publishing logs across platforms.
    """
    __tablename__ = "published_posts"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    digest_id: Mapped[Optional[str]] = mapped_column(
        String(36), 
        ForeignKey("digests.id"), 
        index=True, 
        nullable=True
    )
    event_id: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("events.id"),
        index=True,
        nullable=True
    )
    post_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        index=True,
        nullable=True
    )
    
    # Allowed: TELEGRAM, INSTAGRAM, THREADS, TWITTER, WEBSITE
    platform: Mapped[str] = mapped_column(
        String(50), 
        index=True, 
        nullable=False
    )
    external_id: Mapped[Optional[str]] = mapped_column(
        String(255), 
        nullable=True
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict
    )
    published_at: Mapped[datetime] = mapped_column(
        DateTime, 
        index=True, 
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), 
        nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "event_id",
            "platform",
            "post_type",
            name="uq_publication_tracking"
        ),
    )

    # Relationships
    digest: Mapped[Optional["Digest"]] = relationship(
        "Digest", 
        back_populates="published_posts"
    )
    event: Mapped[Optional["Event"]] = relationship(
        "Event",
        back_populates="published_posts"
    )

