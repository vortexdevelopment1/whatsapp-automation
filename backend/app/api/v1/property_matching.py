import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_db
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_match import PropertyMatch
from app.models.property_matching_run import PropertyMatchingRun
from app.models.enums import PropertyMatchStatus
from app.schemas.property_match import (
    PropertyMatchResponse,
    PropertyMatchingRunResponse,
    RunMatchingRequest,
    RunMatchingResponse,
    PropertyMatchOverrideRequest,
    ScoreMatchesRequest,
    ScoreMatchesResponse,
    PropertyMatchStaleRequest,
)
from app.schemas.audit import AuditLogCreate
from app.services.property_candidate_service import PropertyCandidateService
from app.services.property_matching_service import PropertyMatchingService
from app.services.property_scoring_config import PropertyScoringConfig, DEFAULT_SCORING_CONFIG

router = APIRouter(tags=["property-matching"])

# Module-level variable for active scoring configuration
_active_scoring_config = DEFAULT_SCORING_CONFIG


@router.post(
    "/leads/{lead_id}/property-matching/run",
    response_model=RunMatchingResponse,
    status_code=status.HTTP_200_OK,
)
def run_property_matching(
    lead_id: uuid.UUID,
    payload: Optional[RunMatchingRequest] = None,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Module 4 Phase 3:
    Executes Candidate Search & Hard Filters for a QUALIFIED lead.
    Enforces Module 3 qualification handoff.
    """
    service = PropertyCandidateService(db)
    config = payload.config if payload else None

    matching_run = service.run_candidate_search(
        lead_id=lead_id,
        config=config,
        actor_id=x_admin_id,
    )

    return RunMatchingResponse(
        run_id=matching_run.id,
        status=matching_run.status,
        total_inventory_considered=matching_run.total_inventory_considered,
        eligible_candidates=matching_run.eligible_candidates,
        filtered_candidates=matching_run.filtered_candidates,
        needs_review_candidates=matching_run.needs_review_candidates,
        config_version=matching_run.config_version,
    )


@router.post(
    "/leads/{lead_id}/property-matching/score",
    response_model=ScoreMatchesResponse,
    status_code=status.HTTP_200_OK,
)
def score_property_matches(
    lead_id: uuid.UUID,
    payload: Optional[ScoreMatchesRequest] = None,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """
    Module 4 Phase 4:
    Scores and ranks ONLY the candidate properties that passed Phase 3 hard filters.
    Applies configurable weights, deterministic tie-breaking, and transparent explainability.
    """
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    global _active_scoring_config
    config = payload.config if (payload and payload.config) else _active_scoring_config

    service = PropertyMatchingService(db)
    result = service.score_and_rank_lead_candidates(
        lead_id=lead_id,
        config=config,
        actor_id=x_admin_id,
    )

    return ScoreMatchesResponse(
        lead_id=lead_id,
        scored=result["scored"],
        ready_for_agent_verification=result["ready_for_agent_verification"],
        below_threshold=result["below_threshold"],
        top_score=result["top_score"],
        scoring_config_version=result["scoring_config_version"],
    )


@router.get(
    "/property-matching/scoring-config",
    response_model=PropertyScoringConfig,
)
def get_scoring_configuration():
    """Retrieves current active scoring configuration."""
    global _active_scoring_config
    return _active_scoring_config


@router.patch(
    "/property-matching/scoring-config",
    response_model=PropertyScoringConfig,
)
def update_scoring_configuration(
    new_config: PropertyScoringConfig,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
):
    """Updates active scoring configuration weights and thresholds (requires operator/admin)."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    global _active_scoring_config
    _active_scoring_config = new_config
    return _active_scoring_config


@router.get(
    "/leads/{lead_id}/property-matching/runs",
    response_model=List[PropertyMatchingRunResponse],
)
def list_lead_matching_runs(
    lead_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Lists historical property matching runs for a lead."""
    runs = (
        db.query(PropertyMatchingRun)
        .filter(PropertyMatchingRun.lead_id == lead_id)
        .order_by(PropertyMatchingRun.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    return runs


@router.get(
    "/leads/{lead_id}/property-matches",
    response_model=List[PropertyMatchResponse],
)
def list_lead_property_matches(
    lead_id: uuid.UUID,
    match_status: Optional[PropertyMatchStatus] = Query(None, alias="status"),
    min_score: Optional[float] = Query(None, ge=0.0, le=100.0),
    availability_status: Optional[str] = None,
    property_type: Optional[str] = None,
    is_stale: Optional[bool] = None,
    sort_by: Optional[str] = Query("rank", regex="^(rank|score|price|created_at)$"),
    sort_order: Optional[str] = Query("asc", regex="^(asc|desc)$"),
    run_id: Optional[uuid.UUID] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """
    List candidate property matches for a lead with filtering, score ranking, and presentation metadata.
    """
    query = (
        db.query(PropertyMatch)
        .options(
            joinedload(PropertyMatch.property),
            joinedload(PropertyMatch.listing),
        )
        .filter(PropertyMatch.lead_id == lead_id)
    )

    if match_status:
        query = query.filter(PropertyMatch.match_status == match_status.value)
    if min_score is not None:
        query = query.filter(PropertyMatch.match_score >= min_score)
    if availability_status:
        query = query.filter(PropertyMatch.availability_status == availability_status)
    if is_stale is not None:
        query = query.filter(PropertyMatch.is_stale == is_stale)
    if run_id:
        query = query.filter(PropertyMatch.matching_run_id == run_id)

    if property_type:
        query = query.join(PropertyMatch.property).filter(Property.property_type == property_type)

    # Sorting
    if sort_by == "rank":
        query = query.order_by(
            PropertyMatch.rank.asc().nullslast(),
            PropertyMatch.match_score.desc().nullslast(),
        )
    elif sort_by == "score":
        if sort_order == "asc":
            query = query.order_by(PropertyMatch.match_score.asc().nullslast())
        else:
            query = query.order_by(PropertyMatch.match_score.desc().nullslast())
    elif sort_by == "price":
        query = query.join(PropertyMatch.listing)
        if sort_order == "desc":
            query = query.order_by(PropertyListing.asking_price.desc().nullslast())
        else:
            query = query.order_by(PropertyListing.asking_price.asc().nullslast())
    else:
        query = query.order_by(PropertyMatch.created_at.desc())

    matches = query.offset(skip).limit(limit).all()

    result = []
    for m in matches:
        resp = PropertyMatchResponse.model_validate(m)
        if m.property:
            resp.property_data = {
                "id": str(m.property.id),
                "canonical_name": m.property.canonical_name,
                "building_name": m.property.building_name,
                "address_line_1": m.property.address_line_1,
                "address_line_2": m.property.address_line_2,
                "unit_number": m.property.unit_number,
                "postal_code": m.property.postal_code,
                "city": m.property.city,
                "district": m.property.district,
                "property_type": m.property.property_type.value if hasattr(m.property.property_type, "value") else str(m.property.property_type),
                "bedrooms": m.property.bedrooms,
                "bathrooms": float(m.property.bathrooms) if m.property.bathrooms else None,
                "size_sqft": float(m.property.size_sqft) if m.property.size_sqft else None,
                "furnishing": m.property.furnishing.value if hasattr(m.property.furnishing, "value") else str(m.property.furnishing),
            }
        if m.listing:
            resp.listing_data = {
                "id": str(m.listing.id),
                "asking_price": float(m.listing.asking_price) if m.listing.asking_price else None,
                "currency": m.listing.currency,
                "availability_status": m.listing.availability_status.value if hasattr(m.listing.availability_status, "value") else str(m.listing.availability_status),
                "available_from": m.listing.available_from.isoformat() if m.listing.available_from else None,
                "lease_min_months": m.listing.lease_min_months,
                "lease_max_months": m.listing.lease_max_months,
                "listing_status": m.listing.listing_status.value if hasattr(m.listing.listing_status, "value") else str(m.listing.listing_status),
            }
        result.append(resp)

    return result


@router.get(
    "/property-matches/{match_id}",
    response_model=PropertyMatchResponse,
)
def get_property_match(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Gets detailed property match evaluation including score breakdown, explanations, and risk flags."""
    m = (
        db.query(PropertyMatch)
        .options(
            joinedload(PropertyMatch.property),
            joinedload(PropertyMatch.listing),
        )
        .filter(PropertyMatch.id == match_id)
        .first()
    )
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property match record '{match_id}' not found.",
        )

    resp = PropertyMatchResponse.model_validate(m)
    if m.property:
        resp.property_data = {
            "id": str(m.property.id),
            "canonical_name": m.property.canonical_name,
            "building_name": m.property.building_name,
            "address_line_1": m.property.address_line_1,
            "address_line_2": m.property.address_line_2,
            "unit_number": m.property.unit_number,
            "postal_code": m.property.postal_code,
            "city": m.property.city,
            "district": m.property.district,
            "property_type": m.property.property_type.value if hasattr(m.property.property_type, "value") else str(m.property.property_type),
            "bedrooms": m.property.bedrooms,
            "bathrooms": float(m.property.bathrooms) if m.property.bathrooms else None,
            "size_sqft": float(m.property.size_sqft) if m.property.size_sqft else None,
            "furnishing": m.property.furnishing.value if hasattr(m.property.furnishing, "value") else str(m.property.furnishing),
        }
    if m.listing:
        resp.listing_data = {
            "id": str(m.listing.id),
            "asking_price": float(m.listing.asking_price) if m.listing.asking_price else None,
            "currency": m.listing.currency,
            "availability_status": m.listing.availability_status.value if hasattr(m.listing.availability_status, "value") else str(m.listing.availability_status),
            "available_from": m.listing.available_from.isoformat() if m.listing.available_from else None,
            "lease_min_months": m.listing.lease_min_months,
            "lease_max_months": m.listing.lease_max_months,
            "listing_status": m.listing.listing_status.value if hasattr(m.listing.listing_status, "value") else str(m.listing.listing_status),
        }
    return resp


@router.post(
    "/property-matches/{match_id}/mark-stale",
    response_model=PropertyMatchResponse,
)
def mark_property_match_stale(
    match_id: uuid.UUID,
    payload: PropertyMatchStaleRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """Flags a match score as stale when underlying property/listing or requirement changes."""
    m = db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
    if not m:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Property match '{match_id}' not found.",
        )
    m.is_stale = True
    m.stale_reason = payload.reason
    db.commit()
    db.refresh(m)

    service = PropertyMatchingService(db)
    service.audit_repo.log(
        AuditLogCreate(
            actor_id=x_admin_id,
            action="PROPERTY_MATCH_STALE_MARKED",
            entity_type="property_match",
            entity_id=str(m.id),
            new_value={"reason": payload.reason},
        )
    )

    return get_property_match(match_id, db=db)


@router.post(
    "/property-matches/{match_id}/override",
    response_model=PropertyMatchResponse,
)
def override_property_match(
    match_id: uuid.UUID,
    payload: PropertyMatchOverrideRequest,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """
    Operator manual override:
    Modifies match status (e.g. promoting a candidate to READY_FOR_AGENT_VERIFICATION or review)
    while preserving the underlying hard-filter evaluation and system match scores for complete explainability.
    """
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")

    if payload.target_status == PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION:
        service = PropertyMatchingService(db)
        updated = service.manual_forward_candidate(
            match_id=match_id,
            target_status=payload.target_status,
            reason=payload.reason,
            actor_id=x_admin_id,
        )
    else:
        cand_service = PropertyCandidateService(db)
        updated = cand_service.manual_override_candidate(
            match_id=match_id,
            target_status=payload.target_status,
            reason=payload.reason,
            actor_id=x_admin_id,
        )

    return get_property_match(match_id, db=db)
