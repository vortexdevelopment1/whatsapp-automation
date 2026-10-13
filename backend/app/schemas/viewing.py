from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.enums import (
    ViewingStatus,
    ViewingConfirmationStatus,
    ViewingLocationType,
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingActorType,
)


# Slot Schemas
class ViewingSlotCreateRequest(BaseModel):
    source: ViewingSlotSource = ViewingSlotSource.HUMAN_OPERATOR
    start_at: datetime
    end_at: Optional[datetime] = None
    timezone: str = "Asia/Singapore"
    source_message_id: Optional[UUID] = None


class ViewingSlotUpdateRequest(BaseModel):
    status: ViewingSlotStatus


class ViewingSlotResponse(BaseModel):
    id: UUID
    viewing_id: UUID
    source: ViewingSlotSource
    start_at: datetime
    end_at: Optional[datetime] = None
    timezone: str
    status: ViewingSlotStatus
    source_message_id: Optional[UUID] = None
    is_mutual_match: bool = False
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Viewing Event Schemas
class ViewingEventResponse(BaseModel):
    id: UUID
    viewing_id: UUID
    event_type: ViewingEventType
    old_status: Optional[str] = None
    new_status: Optional[str] = None
    actor_type: ViewingActorType
    actor_id: Optional[str] = None
    event_metadata: Optional[Dict[str, Any]] = Field(default=None, alias="metadata")
    created_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


# Viewing Request Schemas
class ViewingCreateRequest(BaseModel):
    property_match_id: Optional[UUID] = None
    duration_minutes: Optional[int] = 30
    timezone: Optional[str] = "Asia/Singapore"
    location_type: Optional[ViewingLocationType] = ViewingLocationType.IN_PERSON
    location_text: Optional[str] = None
    meeting_url: Optional[str] = None
    created_by: Optional[str] = "operator"


class ViewingUpdateRequest(BaseModel):
    duration_minutes: Optional[int] = None
    timezone: Optional[str] = None
    location_type: Optional[ViewingLocationType] = None
    location_text: Optional[str] = None
    meeting_url: Optional[str] = None
    outcome_notes: Optional[str] = None


class ViewingTransitionRequest(BaseModel):
    target_status: ViewingStatus
    reason: Optional[str] = None
    actor_type: ViewingActorType = ViewingActorType.OPERATOR
    actor_id: Optional[str] = "operator"


class ViewingCancelRequest(BaseModel):
    reason: Optional[str] = None
    reason_code: Optional[str] = "OPERATOR_ACTION"
    cancelled_by: Optional[str] = "OPERATOR"


class ViewingCompleteRequest(BaseModel):
    notes: Optional[str] = None


class ViewingNoShowRequest(BaseModel):
    actor: str = "TENANT"  # TENANT or PROPERTY_AGENT
    notes: Optional[str] = None


# Viewing Response Schemas
class ViewingPropertySummary(BaseModel):
    property_id: UUID
    canonical_name: Optional[str] = None
    building_name: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None


class ViewingListingSummary(BaseModel):
    listing_id: UUID
    asking_price: Optional[float] = None
    currency: str = "SGD"
    available_from: Optional[str] = None
    lease_min_months: Optional[int] = None


class ViewingAgentSummary(BaseModel):
    agent_id: UUID
    full_name: str
    agency_name: Optional[str] = None
    phone: Optional[str] = None


class ViewingResponse(BaseModel):
    id: UUID
    lead_id: UUID
    shortlist_id: Optional[UUID] = None
    shortlist_item_id: Optional[UUID] = None
    property_match_id: UUID
    property_id: UUID
    listing_id: UUID
    property_agent_id: UUID
    status: ViewingStatus
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    timezone: str
    duration_minutes: int
    location_type: ViewingLocationType
    location_text: Optional[str] = None
    meeting_url: Optional[str] = None
    tenant_confirmation_status: ViewingConfirmationStatus
    agent_confirmation_status: ViewingConfirmationStatus
    schedule_version: int = 1
    reschedule_count: int
    previous_scheduled_start_at: Optional[datetime] = None
    previous_scheduled_end_at: Optional[datetime] = None
    reschedule_reason: Optional[str] = None
    cancellation_reason: Optional[str] = None
    cancelled_by: Optional[str] = None
    cancelled_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    outcome: Optional[str] = None
    outcome_notes: Optional[str] = None
    created_by: str
    created_at: datetime
    updated_at: datetime

    property_summary: Optional[ViewingPropertySummary] = None
    listing_summary: Optional[ViewingListingSummary] = None
    agent_summary: Optional[ViewingAgentSummary] = None
    lead_name: Optional[str] = None

    class Config:
        from_attributes = True


class ViewingDetailResponse(ViewingResponse):
    slots: List[ViewingSlotResponse] = []
    events: List[ViewingEventResponse] = []


class ViewingListResponse(BaseModel):
    total: int
    items: List[ViewingResponse]
