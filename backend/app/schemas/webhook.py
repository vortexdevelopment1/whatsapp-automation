import uuid
from datetime import datetime
from typing import Optional, Any, Dict
from pydantic import BaseModel, ConfigDict
from app.models.enums import WebhookProcessingStatus


class WebhookEventBase(BaseModel):
    provider: str = "meta"
    provider_event_id: Optional[str] = None
    event_type: str
    payload: Dict[str, Any]
    processing_status: WebhookProcessingStatus = WebhookProcessingStatus.RECEIVED
    error_message: Optional[str] = None


class WebhookEventCreate(WebhookEventBase):
    pass


class WebhookEventResponse(WebhookEventBase):
    id: uuid.UUID
    received_at: datetime
    processed_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)
