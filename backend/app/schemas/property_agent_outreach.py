import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

from app.models.enums import (
    PropertyAgentOutreachType,
    PropertyAgentOutreachStatus,
    AgentMappingStatus,
)


class PropertyAgentMappingResult(BaseModel):
    match_id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    property_agent_id: Optional[uuid.UUID] = None
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    phone_raw: Optional[str] = None
    phone_normalized: Optional[str] = None
    mapping_status: AgentMappingStatus
    error_message: Optional[str] = None


class OutreachMessagePreview(BaseModel):
    match_id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    property_agent_id: Optional[uuid.UUID] = None
    recipient_phone: Optional[str] = None
    reference_code: str
    template_id: Optional[uuid.UUID] = None
    message_content: str
    context_variables: Dict[str, Any] = Field(default_factory=dict)


class PropertyAgentOutreachCreate(BaseModel):
    template_id: Optional[uuid.UUID] = None
    outreach_type: PropertyAgentOutreachType = PropertyAgentOutreachType.INITIAL_AVAILABILITY_CHECK
    manual_reason: Optional[str] = None


class PropertyAgentOutreachResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    property_id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    property_match_id: uuid.UUID
    property_agent_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    whatsapp_message_id: Optional[uuid.UUID] = None
    template_id: Optional[uuid.UUID] = None
    outreach_type: PropertyAgentOutreachType
    status: PropertyAgentOutreachStatus
    provider_message_id: Optional[str] = None
    idempotency_key: str
    reference_code: Optional[str] = None
    recipient_phone: Optional[str] = None
    message_content: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    property_title: Optional[str] = None

    class Config:
        from_attributes = True


class BulkAgentOutreachRunRequest(BaseModel):
    max_candidates: Optional[int] = None
    template_id: Optional[uuid.UUID] = None


class BulkAgentOutreachRunResponse(BaseModel):
    lead_id: uuid.UUID
    selected: int
    queued: int
    sent: int
    failed: int
    already_contacted: int
    outreach_records: List[PropertyAgentOutreachResponse] = Field(default_factory=list)


class PropertyAgentConversationMessageItem(BaseModel):
    id: uuid.UUID
    direction: str
    content: Optional[str] = None
    provider_status: Optional[str] = None
    created_at: datetime


class PropertyAgentConversationDetail(BaseModel):
    id: uuid.UUID
    property_agent_id: uuid.UUID
    lead_id: uuid.UUID
    property_id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    property_match_id: uuid.UUID
    conversation_type: str
    status: str
    reference_code: Optional[str] = None
    last_message_at: Optional[datetime] = None
    created_at: datetime
    agent_name: Optional[str] = None
    agency_name: Optional[str] = None
    agent_phone: Optional[str] = None
    property_title: Optional[str] = None
    messages: List[PropertyAgentConversationMessageItem] = Field(default_factory=list)

    class Config:
        from_attributes = True
