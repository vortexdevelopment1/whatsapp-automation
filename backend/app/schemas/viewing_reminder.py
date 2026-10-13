import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from app.models.enums import (
    ViewingReminderParty,
    ViewingReminderType,
    ViewingReminderStatus,
)


class ViewingReminderResponse(BaseModel):
    id: uuid.UUID
    viewing_id: uuid.UUID
    party: ViewingReminderParty
    reminder_type: ViewingReminderType
    offset_minutes: Optional[int] = None
    booking_version: int
    scheduled_for: datetime
    timezone: str
    status: ViewingReminderStatus
    message_id: Optional[uuid.UUID] = None
    provider_message_id: Optional[str] = None
    attempt_count: int
    max_attempts: int
    idempotency_key: str
    sent_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ViewingScheduleHistoryResponse(BaseModel):
    id: uuid.UUID
    viewing_id: uuid.UUID
    version: int
    scheduled_start_at: Optional[datetime] = None
    scheduled_end_at: Optional[datetime] = None
    slot_id: Optional[uuid.UUID] = None
    changed_by: str
    reason: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ViewingRescheduleApiRequest(BaseModel):
    requested_by: str = Field(default="OPERATOR", description="TENANT, PROPERTY_AGENT, or OPERATOR")
    reason: Optional[str] = None
    candidate_slot_start: Optional[datetime] = None
    candidate_slot_end: Optional[datetime] = None


class ViewingCancelApiRequest(BaseModel):
    reason_code: str = Field(default="OPERATOR_ACTION", description="Reason code e.g. TENANT_REQUEST, AGENT_REQUEST, PROPERTY_UNAVAILABLE, SCHEDULING_CONFLICT, OPERATOR_ACTION")
    reason: Optional[str] = None
    cancelled_by: Optional[str] = "OPERATOR"


class ViewingReminderBatchProcessResponse(BaseModel):
    total_processed: int
    results: List[Dict[str, Any]]
