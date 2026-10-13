from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import PropertyMatchStatus, MatchingRunStatus
from app.services.property_matching_config import PropertyMatchingConfig
from app.services.property_scoring_config import PropertyScoringConfig


class PropertyMatchOverrideRequest(BaseModel):
    target_status: PropertyMatchStatus = PropertyMatchStatus.ELIGIBLE_FOR_SCORING
    reason: str = Field(..., min_length=3, max_length=500)


class RunMatchingRequest(BaseModel):
    config: Optional[PropertyMatchingConfig] = None


class ScoreMatchesRequest(BaseModel):
    config: Optional[PropertyScoringConfig] = None


class ScoreMatchesResponse(BaseModel):
    lead_id: UUID
    scored: int
    ready_for_agent_verification: int
    below_threshold: int
    top_score: Optional[float] = None
    scoring_config_version: str


class PropertyMatchStaleRequest(BaseModel):
    reason: str = Field(..., min_length=3, max_length=255)


class PropertyMatchingRunResponse(BaseModel):
    id: UUID
    lead_id: UUID
    qualification_decision_id: Optional[UUID] = None
    config_version: str
    status: MatchingRunStatus
    total_inventory_considered: int
    eligible_candidates: int
    filtered_candidates: int
    needs_review_candidates: int
    scored_candidates: int = 0
    ready_for_verification_candidates: int = 0
    below_threshold_candidates: int = 0
    scoring_config_version: Optional[str] = None
    top_score: Optional[float] = None
    requirement_snapshot: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class RunMatchingResponse(BaseModel):
    run_id: UUID
    status: MatchingRunStatus
    total_inventory_considered: int
    eligible_candidates: int
    filtered_candidates: int
    needs_review_candidates: int
    config_version: str


class PropertyMatchResponse(BaseModel):
    id: UUID
    lead_id: UUID
    property_id: UUID
    listing_id: Optional[UUID] = None
    matching_run_id: Optional[UUID] = None
    match_status: str
    hard_filter_passed: Optional[bool] = None
    hard_filter_result: Optional[Dict[str, Any]] = None
    filter_rule_version: Optional[str] = None
    matching_config_version: Optional[str] = None

    # Phase 4 Scoring & Ranking fields
    match_score: Optional[float] = None
    rank: Optional[int] = None
    score_breakdown: Optional[Dict[str, Any]] = None
    scoring_config_version: Optional[str] = None
    scoring_explanation: Optional[str] = None
    is_stale: bool = False
    stale_reason: Optional[str] = None

    agent_verification_status: Optional[str] = None
    availability_status: Optional[str] = None
    manual_override: bool = False
    manual_override_by: Optional[str] = None
    manual_override_at: Optional[datetime] = None
    manual_override_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    # Joined summary payloads for admin presentation
    property_data: Optional[Dict[str, Any]] = None
    listing_data: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)
