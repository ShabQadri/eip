"""
Settings entity model.
"""

import uuid
from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base
from src.models.mixins import TimestampMixin

class Settings(Base, TimestampMixin):
    """
    Represents global system settings and configuration parameters.
    """
    __tablename__ = "settings"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    article_retention_days: Mapped[int] = mapped_column(
        Integer, 
        default=90, 
        nullable=False
    )
    image_retention_days: Mapped[int] = mapped_column(
        Integer, 
        default=180, 
        nullable=False
    )
    log_retention_days: Mapped[int] = mapped_column(
        Integer, 
        default=30, 
        nullable=False
    )
    breaking_threshold: Mapped[int] = mapped_column(
        Integer, 
        default=80, 
        nullable=False
    )
    digest_threshold: Mapped[int] = mapped_column(
        Integer, 
        default=60, 
        nullable=False
    )
    max_articles_per_digest: Mapped[int] = mapped_column(
        Integer, 
        default=12, 
        nullable=False
    )
    cleanup_hour: Mapped[int] = mapped_column(
        Integer, 
        default=2, 
        nullable=False
    )
    keep_images: Mapped[bool] = mapped_column(
        Boolean, 
        default=True, 
        nullable=False
    )
    metric_retention_days: Mapped[int] = mapped_column(
        Integer,
        default=365,
        nullable=False
    )
