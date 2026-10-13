import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import WhatsAppConnectionStatus


class WhatsAppProfileBase(BaseModel):
    meta_business_account_id: Optional[str] = Field(None, max_length=128)
    phone_number_id: Optional[str] = Field(None, max_length=128)
    display_phone_number: Optional[str] = Field(None, max_length=50)
    business_display_name: Optional[str] = Field(None, max_length=255)


class WhatsAppProfileUpdate(WhatsAppProfileBase):
    connection_status: Optional[WhatsAppConnectionStatus] = None


class WhatsAppProfileResponse(WhatsAppProfileBase):
    id: uuid.UUID
    agent_id: uuid.UUID
    connection_status: WhatsAppConnectionStatus
    webhook_verified: bool
    last_webhook_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
