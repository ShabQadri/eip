"""
PublishedPost Pydantic schemas.
"""

from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

class PublishedPostBase(BaseModel):
    digest_id: Optional[str] = Field(None, max_length=36)
    event_id: Optional[str] = Field(None, max_length=36)
    platform: str = Field(..., max_length=50) # TELEGRAM, INSTAGRAM, THREADS, TWITTER, WEBSITE
    post_type: Optional[str] = Field(None, max_length=50)
    external_id: Optional[str] = Field(None, max_length=255)
    metadata_json: dict = Field(default_factory=dict)
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PublishedPostCreate(PublishedPostBase):
    pass

class PublishedPostUpdate(BaseModel):
    digest_id: Optional[str] = Field(None, max_length=36)
    event_id: Optional[str] = Field(None, max_length=36)
    platform: Optional[str] = Field(None, max_length=50)
    post_type: Optional[str] = Field(None, max_length=50)
    external_id: Optional[str] = Field(None, max_length=255)
    metadata_json: Optional[dict] = None
    published_at: Optional[datetime] = None

class PublishedPostRead(PublishedPostBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
