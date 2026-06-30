"""
ReviewConsensus Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class ReviewConsensusBase(BaseModel):
    event_id: Optional[str] = Field(None, max_length=36)
    title: str = Field(..., max_length=255)
    critic_score: Optional[int] = Field(None, ge=0, le=100)
    audience_score: Optional[int] = Field(None, ge=0, le=100)
    consensus_summary: Optional[str] = Field(None, max_length=2000)
    review_count: int = Field(0, ge=0)
    review_source_count: int = Field(0, ge=0)
    sentiment: Optional[str] = Field(None, max_length=50) # POSITIVE, MIXED, NEGATIVE
    review_articles_count: int = Field(0, ge=0)
    last_review_at: Optional[datetime] = None

class ReviewConsensusCreate(ReviewConsensusBase):
    pass

class ReviewConsensusUpdate(BaseModel):
    event_id: Optional[str] = Field(None, max_length=36)
    title: Optional[str] = Field(None, max_length=255)
    critic_score: Optional[int] = Field(None, ge=0, le=100)
    audience_score: Optional[int] = Field(None, ge=0, le=100)
    consensus_summary: Optional[str] = Field(None, max_length=2000)
    review_count: Optional[int] = Field(None, ge=0)
    review_source_count: Optional[int] = Field(None, ge=0)
    sentiment: Optional[str] = Field(None, max_length=50)
    review_articles_count: Optional[int] = Field(None, ge=0)
    last_review_at: Optional[datetime] = None

class ReviewConsensusRead(ReviewConsensusBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
