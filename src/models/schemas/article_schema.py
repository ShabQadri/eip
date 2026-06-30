"""
Article Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ArticleBase(BaseModel):
    source_id: str = Field(..., max_length=36)
    event_id: Optional[str] = Field(None, max_length=36)
    title: str = Field(..., max_length=512)
    url: str = Field(..., max_length=1024)
    description: Optional[str] = Field(None, max_length=4000)
    author: Optional[str] = Field(None, max_length=255)
    published_at: Optional[datetime] = None
    hash: str = Field(..., max_length=64)
    category: Optional[str] = Field(None, max_length=100)
    importance_score: int = Field(0, ge=0, le=100)
    summary: Optional[str] = Field(None, max_length=4000)
    region: Optional[str] = Field(None, max_length=50)
    is_gossip: bool = False
    is_verified: bool = True
    status: str = Field("new", max_length=50)

class ArticleCreate(ArticleBase):
    pass

class ArticleUpdate(BaseModel):
    source_id: Optional[str] = Field(None, max_length=36)
    event_id: Optional[str] = Field(None, max_length=36)
    title: Optional[str] = Field(None, max_length=512)
    url: Optional[str] = Field(None, max_length=1024)
    description: Optional[str] = Field(None, max_length=4000)
    author: Optional[str] = Field(None, max_length=255)
    published_at: Optional[datetime] = None
    hash: Optional[str] = Field(None, max_length=64)
    category: Optional[str] = Field(None, max_length=100)
    importance_score: Optional[int] = Field(None, ge=0, le=100)
    summary: Optional[str] = Field(None, max_length=4000)
    region: Optional[str] = Field(None, max_length=50)
    is_gossip: Optional[bool] = None
    is_verified: Optional[bool] = None
    status: Optional[str] = Field(None, max_length=50)

class ArticleRead(ArticleBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
