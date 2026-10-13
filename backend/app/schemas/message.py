import uuid
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict
from app.models.enums import MessageDirection, MessageType


class MessageBase(BaseModel):
    whatsapp_profile_id: uuid.UUID
    direction: MessageDirection
    message_type: MessageType = MessageType.TEXT
    sender: Optional[str] = None
    recipient: Optional[str] = None
    content: Optional[str] = None
    provider_status: Optional[str] = None
    raw_payload: Optional[Dict[str, Any]] = None


class MessageCreate(MessageBase):
    provider_message_id: Optional[str] = None


class MessageResponse(MessageBase):
    id: uuid.UUID
    provider_message_id: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
