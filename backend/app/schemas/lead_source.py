import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import LeadSourceType, LeadSourceStatus


class LeadSourceBase(BaseModel):
    name: str
    source_type: LeadSourceType = LeadSourceType.MANUAL
    description: Optional[str] = None
    status: LeadSourceStatus = LeadSourceStatus.ACTIVE


class LeadSourceCreate(LeadSourceBase):
    pass


class LeadSourceUpdate(BaseModel):
    name: Optional[str] = None
    source_type: Optional[LeadSourceType] = None
    description: Optional[str] = None
    status: Optional[LeadSourceStatus] = None


class LeadSourceResponse(LeadSourceBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
