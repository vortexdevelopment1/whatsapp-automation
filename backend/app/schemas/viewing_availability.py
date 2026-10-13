from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.enums import (
    ViewingAvailabilityRequestStatus,
    AgentAvailabilityResponseIntent,
    ViewingCorrelationStatus,
    ViewingSlotSource,
    ViewingSlotStatus,
)
from app.schemas.viewing import ViewingSlotResponse


class ExtractedSlotItem(BaseModel):
    start_at: datetime
    end_at: Optional[datetime] = None
    timezone: str = "Asia/Singapore"
    confidence: float = 1.0
    duration_minutes: Optional[int] = None
    is_window: bool = False


class ViewingAgentAvailabilityRequestCreate(BaseModel):
    actor_id: Optional[str] = "operator"
    custom_message: Optional[str] = None
    tenant_broad_availability: Optional[str] = None


class ViewingAvailabilityRequestResponse(BaseModel):
    id: UUID
    viewing_id: UUID
    lead_id: UUID
    property_match_id: UUID
    listing_id: UUID
    property_agent_id: UUID
    conversation_id: Optional[UUID] = None
    status: ViewingAvailabilityRequestStatus
    provider_message_id: Optional[str] = None
    idempotency_key: str
    outbound_message_text: Optional[str] = None
    raw_response_text: Optional[str] = None
    response_intent: Optional[AgentAvailabilityResponseIntent] = None
    correlation_status: ViewingCorrelationStatus
    agent_notes: Optional[str] = None
    sent_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    read_at: Optional[datetime] = None
    replied_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ViewingAgentAvailabilityStatusResponse(BaseModel):
    viewing_id: UUID
    viewing_status: str
    latest_request: Optional[ViewingAvailabilityRequestResponse] = None
    property_agent: Dict[str, Any]
    current_slots: List[ViewingSlotResponse]
    agent_notes: Optional[str] = None
    correlation_status: Optional[str] = None
    needs_human_review: bool = False


class ViewingMessageAnalysisRequest(BaseModel):
    actor_id: Optional[str] = "operator"
    override_viewing_id: Optional[UUID] = None


class AgentMessageManualCorrelationRequest(BaseModel):
    viewing_id: UUID
    reason: str
    actor_id: Optional[str] = "operator"


class AgentAvailabilityExtractionResult(BaseModel):
    intent: AgentAvailabilityResponseIntent
    slots: List[ExtractedSlotItem] = []
    agent_notes: Optional[str] = None
    needs_clarification: bool = False
    property_unavailable: bool = False
    confidence: float = 1.0
    correlation_status: ViewingCorrelationStatus
    matched_viewing_id: Optional[UUID] = None
    matched_request_id: Optional[UUID] = None
    candidate_viewing_ids: List[UUID] = []
    raw_response: str


# ==============================================================================
# MODULE 5 PHASE 4: TENANT AVAILABILITY & SLOT MATCHING SCHEMAS
# ==============================================================================
from app.models.enums import TenantAvailabilityResponseIntent, SlotMatchType


class TenantAvailabilityWindowItem(BaseModel):
    start_at: datetime
    end_at: datetime
    timezone: str = "Asia/Singapore"
    confidence: float = 1.0


class TenantViewingAvailabilityRequestCreate(BaseModel):
    actor_id: Optional[str] = "operator"
    strategy: Optional[str] = "OFFER_AGENT_SLOTS"  # OFFER_AGENT_SLOTS or ASK_GENERAL
    custom_message: Optional[str] = None


class TenantViewingAvailabilityRequestResponse(BaseModel):
    viewing_id: UUID
    lead_id: UUID
    strategy: str
    message_sent: bool
    provider_message_id: Optional[str] = None
    offered_slots: List[ViewingSlotResponse] = []
    sent_at: Optional[datetime] = None


class TenantAvailabilityUnderstandingResult(BaseModel):
    intent: TenantAvailabilityResponseIntent
    selected_slot_id: Optional[UUID] = None
    availability_windows: List[TenantAvailabilityWindowItem] = []
    correlated_viewing_id: Optional[UUID] = None
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    raw_response: str
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        populate_by_name = True


class MutualSlotMatchItem(BaseModel):
    start_at: datetime
    end_at: datetime
    timezone: str
    match_type: SlotMatchType
    agent_slot_id: Optional[UUID] = None
    tenant_slot_id: Optional[UUID] = None
    reason: str
    is_proposed: bool = False


class ViewingSlotMatchingResult(BaseModel):
    viewing_id: UUID
    total_mutual_slots: int
    mutual_slots: List[MutualSlotMatchItem] = []

    agent_slots_count: int
    tenant_windows_count: int
    status: str
    recommended_slot: Optional[MutualSlotMatchItem] = None

    class Config:
        populate_by_name = True


class ViewingTenantAvailabilityStatusResponse(BaseModel):
    viewing_id: UUID
    viewing_status: str
    agent_slots: List[ViewingSlotResponse]
    tenant_slots: List[ViewingSlotResponse]
    mutual_slots: List[MutualSlotMatchItem]
    current_proposed_slot: Optional[ViewingSlotResponse] = None
    needs_human_review: bool = False


class CandidateSlotProposeRequest(BaseModel):
    slot_id: Optional[UUID] = None
    start_at: Optional[datetime] = None
    end_at: Optional[datetime] = None
    timezone: Optional[str] = "Asia/Singapore"
    actor_id: Optional[str] = "operator"
    reason: Optional[str] = None


class ManualTenantAvailabilityCreate(BaseModel):
    windows: List[TenantAvailabilityWindowItem]
    actor_id: Optional[str] = "operator"
    notes: Optional[str] = None


class TenantAvailabilityMatchRequest(BaseModel):
    selected_slot_id: Optional[UUID] = None
    tenant_windows: Optional[List[TenantAvailabilityWindowItem]] = None
    duration_minutes: Optional[int] = None
    interval_minutes: Optional[int] = None


