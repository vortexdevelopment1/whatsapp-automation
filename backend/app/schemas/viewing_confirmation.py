"""
Viewing Confirmation & Booking Schemas - Module 5 Phase 5
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.enums import (
    ViewingConfirmationStatus,
    TenantConfirmationResponseIntent,
    AgentConfirmationResponseIntent,
    ConfirmationParty,
)
from app.schemas.viewing import ViewingSlotResponse


class ViewingConfirmationRequestCreate(BaseModel):
    actor_id: Optional[str] = "operator"
    custom_message: Optional[str] = None


class ViewingConfirmationRequestResponse(BaseModel):
    viewing_id: UUID
    party: ConfirmationParty
    status: ViewingConfirmationStatus
    message_sent: bool
    provider_message_id: Optional[str] = None
    sent_at: Optional[datetime] = None
    proposed_start_at: Optional[datetime] = None
    proposed_end_at: Optional[datetime] = None


class TenantConfirmationUnderstandingResult(BaseModel):
    intent: TenantConfirmationResponseIntent
    correlated_viewing_id: Optional[UUID] = None
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    raw_response: str
    metadata: Optional[Dict[str, Any]] = None


class AgentConfirmationUnderstandingResult(BaseModel):
    intent: AgentConfirmationResponseIntent
    correlated_viewing_id: Optional[UUID] = None
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    raw_response: str
    metadata: Optional[Dict[str, Any]] = None


class ViewingConfirmationStatusOverview(BaseModel):
    viewing_id: UUID
    booking_reference: str
    viewing_status: str
    tenant_confirmation_status: ViewingConfirmationStatus
    agent_confirmation_status: ViewingConfirmationStatus
    proposed_slot: Optional[ViewingSlotResponse] = None
    booked_slot: Optional[ViewingSlotResponse] = None
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    timezone: str
    location_type: str
    location_text: Optional[str] = None
    meeting_url: Optional[str] = None
    policy_summary: Dict[str, Any]
    can_finalize: bool = False
    is_confirmed: bool = False


class ViewingManualConfirmationRequest(BaseModel):
    actor_id: Optional[str] = "operator"
    reason: str
    notes: Optional[str] = None


class ViewingDeclineRequest(BaseModel):
    actor_id: Optional[str] = "operator"
    reason: str


class ViewingFinalizeBookingResponse(BaseModel):
    viewing_id: UUID
    booking_reference: str
    status: str
    booked_slot_id: UUID
    scheduled_start_at: datetime
    scheduled_end_at: datetime
    timezone: str
    location_text: Optional[str] = None
    meeting_url: Optional[str] = None
    tenant_notified: bool = False
    agent_notified: bool = False
    confirmed_at: datetime
