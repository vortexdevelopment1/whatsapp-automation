import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    AgentResponseIntent,
    AvailabilityVerificationStatus,
    AvailabilityVerificationSource,
    AgentCorrelationStatus,
)


class AgentResponseFieldExtraction(BaseModel):
    value: Any
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    explicit: bool = True
    needs_confirmation: bool = False


class AgentResponseExtractionResult(BaseModel):
    intent: AgentResponseIntent = AgentResponseIntent.AVAILABLE
    fields: Dict[str, AgentResponseFieldExtraction] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_reasons: List[str] = Field(default_factory=list)
    raw_summary: Optional[str] = None
    overall_confidence: float = Field(ge=0.0, le=1.0, default=1.0)


class AvailabilityVerificationBase(BaseModel):
    availability_status: str
    asking_price: Optional[Decimal] = None
    currency: Optional[str] = "SGD"
    available_from: Optional[date] = None
    minimum_lease_months: Optional[int] = None
    maximum_lease_months: Optional[int] = None
    furnishing: Optional[str] = None
    viewing_possible: Optional[bool] = None
    viewing_notes: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    special_restrictions: Optional[Dict[str, Any]] = None
    extracted_fields: Optional[Dict[str, Any]] = None
    verification_status: Optional[str] = "CONFIRMED"
    verification_source: Optional[str] = "AGENT_REPLY"
    confidence_summary: Optional[Dict[str, Any]] = None
    overall_confidence: Optional[float] = None
    notes: Optional[str] = None


class AvailabilityVerificationCreate(AvailabilityVerificationBase):
    property_match_id: Optional[uuid.UUID] = None
    listing_id: Optional[uuid.UUID] = None
    property_agent_id: Optional[uuid.UUID] = None
    outreach_id: Optional[uuid.UUID] = None
    source_message_id: Optional[uuid.UUID] = None
    intent: Optional[str] = None
    ai_call_id: Optional[uuid.UUID] = None


class AvailabilityVerificationResponse(AvailabilityVerificationBase):
    id: uuid.UUID
    property_match_id: Optional[uuid.UUID] = None
    listing_id: Optional[uuid.UUID] = None
    property_agent_id: Optional[uuid.UUID] = None
    outreach_id: Optional[uuid.UUID] = None
    source_message_id: Optional[uuid.UUID] = None
    intent: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CorrelationResolveRequest(BaseModel):
    property_match_id: uuid.UUID
    reason: str = Field(min_length=3, max_length=500)


class ManualVerificationOverrideRequest(BaseModel):
    availability_status: str = Field(description="AVAILABLE, UNAVAILABLE, CONDITIONAL, NEEDS_REVIEW")
    asking_price: Optional[Decimal] = None
    currency: Optional[str] = "SGD"
    available_from: Optional[date] = None
    minimum_lease_months: Optional[int] = None
    maximum_lease_months: Optional[int] = None
    furnishing: Optional[str] = None
    viewing_possible: Optional[bool] = None
    viewing_notes: Optional[str] = None
    conditions: Optional[Dict[str, Any]] = None
    special_restrictions: Optional[Dict[str, Any]] = None
    reason: str = Field(min_length=3, max_length=500)


class AgentResponseAnalysisResponse(BaseModel):
    status: str
    message_id: uuid.UUID
    correlation: Dict[str, Any]
    extraction: Optional[Dict[str, Any]] = None
    verification: Optional[AvailabilityVerificationResponse] = None
    match_status: Optional[str] = None
    score_marked_stale: bool = False
    compatibility_rechecked: bool = False
    compatibility_result: Optional[Dict[str, Any]] = None
