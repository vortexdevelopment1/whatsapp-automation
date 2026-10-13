import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class PropertyAgentFollowUpResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    property_match_id: uuid.UUID
    listing_id: Optional[uuid.UUID] = None
    property_agent_id: uuid.UUID
    outreach_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    followup_type: str
    attempt_number: int
    status: str
    due_at: datetime
    sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    cancellation_reason: Optional[str] = None
    idempotency_key: str
    message_content: Optional[str] = None
    whatsapp_message_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ManualFollowUpRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Reason for sending manual follow-up")


class CancelFollowUpRequest(BaseModel):
    reason: Optional[str] = Field(default="Operator cancelled", description="Reason for cancelling follow-up")


class FallbackPreviewResponse(BaseModel):
    match_id: uuid.UUID
    current_match_status: str
    current_outreach_status: Optional[str] = None
    recommended_action: str
    reason: Optional[str] = None
    alternate_listing: Optional[Dict[str, Any]] = None
    next_property_match: Optional[Dict[str, Any]] = None
    total_agent_contacts: int
    max_total_agent_contacts: int


class ExecuteFallbackRequest(BaseModel):
    reason: Optional[str] = Field(default=None, description="Operator reason for executing fallback")


class ExecuteFallbackResponse(BaseModel):
    status: str
    action: str
    match_id: uuid.UUID
    new_outreach_id: Optional[str] = None
    new_match_id: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
