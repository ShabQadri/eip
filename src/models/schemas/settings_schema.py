"""
Settings Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SettingsBase(BaseModel):
    article_retention_days: int = Field(90, ge=1)
    image_retention_days: int = Field(180, ge=1)
    log_retention_days: int = Field(30, ge=1)
    breaking_threshold: int = Field(80, ge=0, le=100)
    digest_threshold: int = Field(60, ge=0, le=100)
    max_articles_per_digest: int = Field(12, ge=1)
    cleanup_hour: int = Field(2, ge=0, le=23)
    keep_images: bool = True
    metric_retention_days: int = Field(365, ge=1)

class SettingsCreate(SettingsBase):
    pass

class SettingsUpdate(BaseModel):
    article_retention_days: Optional[int] = Field(None, ge=1)
    image_retention_days: Optional[int] = Field(None, ge=1)
    log_retention_days: Optional[int] = Field(None, ge=1)
    breaking_threshold: Optional[int] = Field(None, ge=0, le=100)
    digest_threshold: Optional[int] = Field(None, ge=0, le=100)
    max_articles_per_digest: Optional[int] = Field(None, ge=1)
    cleanup_hour: Optional[int] = Field(None, ge=0, le=23)
    keep_images: Optional[bool] = None
    metric_retention_days: Optional[int] = Field(None, ge=1)

class SettingsRead(SettingsBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
