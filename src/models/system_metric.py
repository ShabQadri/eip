"""
SystemMetric entity model with custom TZDateTime for SQLite timezone handling.
"""

import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Float, DateTime, JSON, Index
from sqlalchemy.types import TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column
from src.database.base import Base

class TZDateTime(TypeDecorator):
    """
    SQLAlchemy TypeDecorator to ensure that timezone-aware datetime values 
    are properly set/retrieved with UTC timezone, even on SQLite.
    """
    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
        return value

    def process_result_value(self, value, dialect):
        if value is not None:
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
        return value

class SystemMetric(Base):
    """
    Tracks operational system metrics and production analytics.
    """
    __tablename__ = "system_metrics"

    id: Mapped[str] = mapped_column(
        String(36), 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    metric_name: Mapped[str] = mapped_column(
        String(100), 
        index=True, 
        nullable=False
    )
    metric_value: Mapped[float] = mapped_column(
        Float, 
        nullable=False
    )
    aggregation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False
    )
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False
    )
    metadata_json: Mapped[dict] = mapped_column(
        JSON, 
        nullable=False, 
        default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        TZDateTime(), 
        index=True, 
        default=lambda: datetime.now(timezone.utc), 
        nullable=False
    )

    __table_args__ = (
        Index("ix_system_metrics_metric_name_created_at", "metric_name", "created_at"),
        Index("ix_system_metrics_source_created_at", "source", "created_at"),
    )
