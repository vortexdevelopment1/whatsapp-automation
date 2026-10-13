from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, Field

from app.models.enums import PropertyInterestStatus, TenantInterestIntent


class TenantSafePropertySummary(BaseModel):
    property_match_id: UUID
    property_id: UUID
    listing_id: UUID
    name: str
    building_name: Optional[str] = None
    address: Optional[str] = None
    district: Optional[str] = None
    property_type: str
    bedrooms: Optional[int] = None
    furnishing: Optional[str] = None
    asking_price: Optional[float] = None
    currency: str = "SGD"
    available_from: Optional[str] = None
    lease_min_months: Optional[int] = None
    source_url: Optional[str] = None
    summary_text: str

    class Config:
        from_attributes = True


class PropertyInterestResponse(BaseModel):
    id: UUID
    lead_id: UUID
    property_match_id: UUID
    shortlist_id: Optional[UUID] = None
    shortlist_item_id: Optional[UUID] = None
    viewing_id: Optional[UUID] = None
    status: PropertyInterestStatus
    source_message_id: Optional[UUID] = None
    presented_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    presented_price: Optional[float] = None
    presented_currency: str = "SGD"
    presented_availability: Optional[str] = None
    presentation_notes: Optional[str] = None
    last_intent: Optional[TenantInterestIntent] = None
    tenant_notes: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    property_summary: Optional[TenantSafePropertySummary] = None

    class Config:
        from_attributes = True


class PropertyInterestListResponse(BaseModel):
    total: int
    items: List[PropertyInterestResponse]


class PropertyInterestUpdateManualRequest(BaseModel):
    status: PropertyInterestStatus
    tenant_notes: Optional[str] = None
    actor_id: Optional[str] = "operator"


class PropertyPresentationResult(BaseModel):
    success: bool
    lead_id: UUID
    presented_count: int
    items: List[PropertyInterestResponse]
    message_sent: bool
    message_id: Optional[str] = None
    note: Optional[str] = None


class TenantInterestProcessRequest(BaseModel):
    message_content: str
    interactive_payload: Optional[str] = None
    inbound_message_id: Optional[UUID] = None


class TenantInterestProcessResult(BaseModel):
    intent: TenantInterestIntent
    correlated_property_match_id: Optional[UUID] = None
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_question: Optional[str] = None
    viewing_created: bool = False
    viewing_id: Optional[UUID] = None
    response_text: Optional[str] = None
    property_interest: Optional[PropertyInterestResponse] = None
