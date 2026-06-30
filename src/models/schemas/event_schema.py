"""
Event Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class EventBase(BaseModel):
    canonical_title: str = Field(..., max_length=255)
    display_title: Optional[str] = Field(None, max_length=255)
    event_type: str = Field(..., max_length=100)
    importance_score: int = Field(0, ge=0, le=100)
    summary: Optional[str] = Field(None, max_length=2000)
    region: Optional[str] = Field(None, max_length=50)       # HOLLYWOOD, INDIA, PAN_INDIA, KOREA, ANIME, GLOBAL
    franchise: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)        # ANNOUNCED, IN_PRODUCTION, RELEASED, CANCELLED, COMPLETED
    is_gossip: bool = False
    is_featured: bool = False
    source_count: int = 0
    article_count: int = 0
    first_article_at: Optional[datetime] = None
    last_article_at: Optional[datetime] = None
    aliases_json: list = Field(default_factory=list)
    source_domains_json: list = Field(default_factory=list)
    event_pattern: Optional[str] = Field(None, max_length=100)
    season_number: Optional[int] = None
    event_year: Optional[int] = None
    published: bool = False

class EventCreate(EventBase):
    pass

class EventUpdate(BaseModel):
    canonical_title: Optional[str] = Field(None, max_length=255)
    display_title: Optional[str] = Field(None, max_length=255)
    event_type: Optional[str] = Field(None, max_length=100)
    importance_score: Optional[int] = Field(None, ge=0, le=100)
    summary: Optional[str] = Field(None, max_length=2000)
    region: Optional[str] = Field(None, max_length=50)
    franchise: Optional[str] = Field(None, max_length=255)
    status: Optional[str] = Field(None, max_length=50)
    is_gossip: Optional[bool] = None
    is_featured: Optional[bool] = None
    source_count: Optional[int] = None
    article_count: Optional[int] = None
    first_article_at: Optional[datetime] = None
    last_article_at: Optional[datetime] = None
    aliases_json: Optional[list] = None
    source_domains_json: Optional[list] = None
    event_pattern: Optional[str] = Field(None, max_length=100)
    season_number: Optional[int] = None
    event_year: Optional[int] = None
    published: Optional[bool] = None

class EventRead(EventBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
