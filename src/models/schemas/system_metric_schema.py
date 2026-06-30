"""
SystemMetric Pydantic schemas.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

class SystemMetricBase(BaseModel):
    metric_name: str = Field(..., max_length=100)
    metric_value: float
    aggregation_type: str = Field(..., max_length=20)
    source: str = Field(..., max_length=100)
    metadata_json: dict = Field(default_factory=dict)
    created_at: Optional[datetime] = None

class SystemMetricCreate(SystemMetricBase):
    pass

class SystemMetricUpdate(BaseModel):
    metric_name: Optional[str] = Field(None, max_length=100)
    metric_value: Optional[float] = None
    aggregation_type: Optional[str] = Field(None, max_length=20)
    source: Optional[str] = Field(None, max_length=100)
    metadata_json: Optional[dict] = None
    created_at: Optional[datetime] = None

class SystemMetricRead(SystemMetricBase):
    id: str
    created_at: datetime

    model_config = {
        "from_attributes": True
    }
