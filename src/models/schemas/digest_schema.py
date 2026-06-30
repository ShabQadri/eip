"""
Digest Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class DigestBase(BaseModel):
    digest_type: str = Field(..., max_length=50) # MORNING, EVENING, BREAKING, WEEKLY
    content: str = Field(..., max_length=8000)
    image_path: Optional[str] = Field(None, max_length=512)
    published_at: Optional[datetime] = None

class DigestCreate(DigestBase):
    pass

class DigestUpdate(BaseModel):
    digest_type: Optional[str] = Field(None, max_length=50)
    content: Optional[str] = Field(None, max_length=8000)
    image_path: Optional[str] = Field(None, max_length=512)
    published_at: Optional[datetime] = None

class DigestRead(DigestBase):
    id: str
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
