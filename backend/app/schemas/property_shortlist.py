from datetime import datetime, date
from decimal import Decimal
from typing import List, Optional, Any, Dict
from uuid import UUID
from pydantic import BaseModel, ConfigDict


class CandidateReadinessResult(BaseModel):
    property_match_id: UUID
    shortlist_status: str
    eligible: bool
    score: Optional[Decimal] = None
    rank: Optional[int] = None
    verification_status: Optional[str] = None
    availability: Optional[str] = None
    reasons: List[str] = []
    warnings: List[str] = []
    explanation: Optional[str] = None
    requires_score_refresh: bool = False


class PropertyShortlistItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    shortlist_id: UUID
    property_match_id: UUID
    position: int
    shortlist_status: str
    score_at_selection: Optional[Decimal] = None
    verification_id: Optional[UUID] = None
    reason_codes: Optional[List[str]] = None
    warnings: Optional[List[str]] = None
    explanation: Optional[str] = None
    manual_override: bool = False
    manual_override_reason: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    # Enriched details
    property_id: Optional[UUID] = None
    listing_id: Optional[UUID] = None
    property_agent_id: Optional[UUID] = None
    property_name: Optional[str] = None
    property_address: Optional[str] = None
    building_name: Optional[str] = None
    district: Optional[str] = None
    property_type: Optional[str] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    size_sqft: Optional[int] = None
    furnishing: Optional[str] = None
    asking_price: Optional[Decimal] = None
    currency: Optional[str] = "SGD"
    available_from: Optional[date] = None
    lease_min_months: Optional[int] = None
    availability_status: Optional[str] = None
    agent_name: Optional[str] = None
    agent_agency: Optional[str] = None
    verified_at: Optional[datetime] = None


class PropertyShortlistResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lead_id: UUID
    matching_run_id: Optional[UUID] = None
    version: int
    status: str
    config_version: str
    created_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    items: List[PropertyShortlistItemResponse] = []


class ShortlistReorderItem(BaseModel):
    property_match_id: UUID
    position: int


class ShortlistReorderRequest(BaseModel):
    items: List[ShortlistReorderItem]


class ManualShortlistAddRequest(BaseModel):
    manual_override_reason: Optional[str] = None
    force_override: bool = False


class DashboardSummaryCards(BaseModel):
    total_candidates: int
    eligible: int
    awaiting_agents: int
    verified_available: int
    conditional: int
    unavailable: int
    needs_review: int
    shortlisted: int


class DashboardFunnelStep(BaseModel):
    step_name: str
    count: int


class CandidateComparisonItem(BaseModel):
    field_name: str
    tenant_requirement: str
    property_value: str
    status: str  # "MATCH", "WARNING", "MISMATCH", "UNKNOWN"


class CandidateDetailItem(BaseModel):
    property_match_id: UUID
    property_id: UUID
    listing_id: Optional[UUID] = None
    property_agent_id: Optional[UUID] = None
    system_rank: Optional[int] = None
    match_score: Optional[Decimal] = None
    is_stale: bool = False
    stale_reason: Optional[str] = None
    property_name: str
    building_name: Optional[str] = None
    address: str
    district: Optional[str] = None
    property_type: str
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    size_sqft: Optional[int] = None
    furnishing: Optional[str] = None
    asking_price: Optional[Decimal] = None
    currency: str = "SGD"
    available_from: Optional[date] = None
    lease_min_months: Optional[int] = None
    availability_status: Optional[str] = None
    agent_verification_status: Optional[str] = None
    agent_name: Optional[str] = None
    agent_agency: Optional[str] = None
    followup_status: Optional[str] = None
    shortlist_status: str
    in_shortlist: bool = False
    shortlist_position: Optional[int] = None
    explanation: Optional[str] = None
    reasons: List[str] = []
    warnings: List[str] = []
    comparison: List[CandidateComparisonItem] = []
    verified_at: Optional[datetime] = None


class PropertyMatchingDashboardResponse(BaseModel):
    lead_id: UUID
    tenant_name: Optional[str] = None
    qualification_status: str
    matching_status: str
    last_matching_run_at: Optional[datetime] = None
    current_shortlist_status: Optional[str] = None
    current_shortlist_version: Optional[int] = None
    current_shortlist_id: Optional[UUID] = None
    module5_ready: bool = False
    summary: DashboardSummaryCards
    funnel: List[DashboardFunnelStep]
    shortlist: Optional[PropertyShortlistResponse] = None
    candidates: List[CandidateDetailItem] = []


class Module5PropertyItem(BaseModel):
    property_match_id: UUID
    property_id: UUID
    listing_id: Optional[UUID] = None
    property_agent_id: Optional[UUID] = None
    shortlist_position: int
    match_score: Optional[Decimal] = None
    availability: str
    asking_price: Optional[Decimal] = None
    currency: str = "SGD"
    available_from: Optional[date] = None
    minimum_lease_months: Optional[int] = None
    verification_id: Optional[UUID] = None
    verified_at: Optional[datetime] = None


class Module5HandoffPayload(BaseModel):
    lead_id: UUID
    shortlist_id: UUID
    shortlist_version: int
    qualification_status: str = "QUALIFIED"
    shortlist_status: str = "READY"
    handoff_status: str = "READY_FOR_VIEWING_COORDINATION"
    generated_at: datetime
    tenant_requirements: Dict[str, Any]
    properties: List[Module5PropertyItem]

