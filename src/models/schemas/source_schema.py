"""
Source Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SourceBase(BaseModel):
    name: str = Field(..., max_length=255)
    domain: str = Field(..., max_length=255)
    rss_url: Optional[str] = Field(None, max_length=512)
    source_type: str = Field(..., max_length=50)  # RSS, YOUTUBE, OFFICIAL, API, MANUAL
    source_tier: int = Field(..., ge=1, le=3)
    policy: str = Field(..., max_length=50)        # HEADLINE_ONLY, SUMMARY_ALLOWED, BLOCKED
    enabled: bool = True
    trust_score: int = Field(100, ge=0, le=100)
    last_successful_fetch: Optional[datetime] = None
    last_failed_fetch: Optional[datetime] = None
    consecutive_failures: int = 0
    disabled_reason: Optional[str] = Field(None, max_length=255)
    disabled_at: Optional[datetime] = None

class SourceCreate(SourceBase):
    pass

class SourceUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    rss_url: Optional[str] = Field(None, max_length=512)
    source_type: Optional[str] = Field(None, max_length=50)
    source_tier: Optional[int] = Field(None, ge=1, le=3)
    policy: Optional[str] = Field(None, max_length=50)
    enabled: Optional[bool] = None
    trust_score: Optional[int] = Field(None, ge=0, le=100)
    last_successful_fetch: Optional[datetime] = None
    last_failed_fetch: Optional[datetime] = None
    consecutive_failures: Optional[int] = None
    disabled_reason: Optional[str] = Field(None, max_length=255)
    disabled_at: Optional[datetime] = None

class SourceRead(SourceBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
