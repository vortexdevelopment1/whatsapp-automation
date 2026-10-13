import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict
from app.models.enums import OutreachType, OutreachStatus


class LeadOutreachBase(BaseModel):
    lead_id: uuid.UUID
    whatsapp_message_id: Optional[uuid.UUID] = None
    template_id: Optional[uuid.UUID] = None
    outreach_type: OutreachType = OutreachType.INITIAL
    status: OutreachStatus = OutreachStatus.QUEUED
    error_message: Optional[str] = None


class LeadOutreachCreate(LeadOutreachBase):
    pass


class LeadOutreachResponse(LeadOutreachBase):
    id: uuid.UUID
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
