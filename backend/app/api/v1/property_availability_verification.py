import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.property_match import PropertyMatch
from app.models.property_availability_verification import PropertyAvailabilityVerification
from app.models.message import WhatsAppMessage
from app.schemas.property_availability_verification import (
    AvailabilityVerificationResponse,
    CorrelationResolveRequest,
    ManualVerificationOverrideRequest,
    AgentResponseAnalysisResponse,
)
from app.services.property_agent_response_understanding_service import (
    PropertyAgentResponseUnderstandingService,
)
from app.services.property_availability_verification_service import (
    PropertyAvailabilityVerificationService,
)

router = APIRouter(tags=["Property Agent Verification"])


@router.post(
    "/property-agent-messages/{message_id}/analyze",
    response_model=AgentResponseAnalysisResponse,
    summary="Analyze agent response message and verify availability",
)
async def analyze_property_agent_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Analyzes an inbound agent response, extracts structured terms,
    validates fields, and applies verification updates to match & listing.
    """
    understanding_service = PropertyAgentResponseUnderstandingService(db)
    verification_service = PropertyAvailabilityVerificationService(db)

    analysis = await understanding_service.analyze_response(
        message_id=message_id,
        actor_id="operator",
    )

    result = verification_service.apply_verification_from_extraction(
        analysis_result=analysis,
        actor_id="operator",
    )

    return AgentResponseAnalysisResponse(
        status=result["status"],
        message_id=message_id,
        correlation=analysis.get("correlation", {}),
        extraction=analysis.get("extraction"),
        verification=result.get("verification"),
        match_status=result.get("match_status"),
        score_marked_stale=result.get("score_marked_stale", False),
        compatibility_rechecked=result.get("compatibility_rechecked", False),
        compatibility_result=result.get("compatibility_result"),
    )


@router.post(
    "/property-agent-messages/{message_id}/resolve-match",
    response_model=AgentResponseAnalysisResponse,
    summary="Manually resolve ambiguous agent message to a specific property match",
)
async def resolve_ambiguous_property_agent_message(
    message_id: uuid.UUID,
    request: CorrelationResolveRequest,
    db: Session = Depends(get_db),
):
    """
    Operator manually links an ambiguous agent message to a specific candidate match
    and triggers structured extraction and availability verification.
    """
    match = db.query(PropertyMatch).filter(PropertyMatch.id == request.property_match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyMatch '{request.property_match_id}' not found.",
        )

    understanding_service = PropertyAgentResponseUnderstandingService(db)
    verification_service = PropertyAvailabilityVerificationService(db)

    analysis = await understanding_service.analyze_response(
        message_id=message_id,
        override_match_id=request.property_match_id,
        actor_id="operator",
    )

    result = verification_service.apply_verification_from_extraction(
        analysis_result=analysis,
        actor_id="operator",
    )

    return AgentResponseAnalysisResponse(
        status=result["status"],
        message_id=message_id,
        correlation=analysis.get("correlation", {}),
        extraction=analysis.get("extraction"),
        verification=result.get("verification"),
        match_status=result.get("match_status"),
        score_marked_stale=result.get("score_marked_stale", False),
        compatibility_rechecked=result.get("compatibility_rechecked", False),
        compatibility_result=result.get("compatibility_result"),
    )


@router.get(
    "/property-matches/{match_id}/availability",
    response_model=Dict[str, Any],
    summary="Get current availability verification details for a property match",
)
def get_property_match_availability(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Retrieves current availability status, agent verification details,
    and latest verification record for a match.
    """
    match = db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
    if not match:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PropertyMatch '{match_id}' not found.",
        )

    latest_verification = (
        db.query(PropertyAvailabilityVerification)
        .filter(PropertyAvailabilityVerification.property_match_id == match_id)
        .order_by(PropertyAvailabilityVerification.created_at.desc())
        .first()
    )

    return {
        "match_id": str(match.id),
        "lead_id": str(match.lead_id),
        "property_id": str(match.property_id),
        "listing_id": str(match.listing_id) if match.listing_id else None,
        "match_status": match.match_status,
        "availability_status": match.availability_status or "NOT_CHECKED",
        "agent_verification_status": match.agent_verification_status or "NOT_CHECKED",
        "is_stale": match.is_stale,
        "stale_reason": match.stale_reason,
        "latest_verification": AvailabilityVerificationResponse.model_validate(latest_verification) if latest_verification else None,
        "listing_asking_price": float(match.listing.asking_price) if match.listing and match.listing.asking_price else None,
        "listing_available_from": match.listing.available_from.isoformat() if match.listing and match.listing.available_from else None,
        "listing_lease_min_months": match.listing.lease_min_months if match.listing else None,
    }


@router.get(
    "/property-matches/{match_id}/verification-history",
    response_model=List[AvailabilityVerificationResponse],
    summary="Get chronological verification history for a property match",
)
def get_property_match_verification_history(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Returns full chronological audit trail of all availability verifications
    (agent replies, manual overrides) for this candidate match.
    """
    records = (
        db.query(PropertyAvailabilityVerification)
        .filter(PropertyAvailabilityVerification.property_match_id == match_id)
        .order_by(PropertyAvailabilityVerification.created_at.desc())
        .all()
    )
    return records


@router.post(
    "/property-matches/{match_id}/availability-override",
    response_model=AvailabilityVerificationResponse,
    summary="Manual operator override of availability verification",
)
def override_property_match_availability(
    match_id: uuid.UUID,
    request: ManualVerificationOverrideRequest,
    actor_id: str = Query("operator", description="Operator identity"),
    db: Session = Depends(get_db),
):
    """
    Allows authorized human operator to manually override availability status,
    price, dates, or lease terms with required reason and audit logging.
    """
    verification_service = PropertyAvailabilityVerificationService(db)
    verification = verification_service.manual_availability_override(
        match_id=match_id,
        request=request,
        actor_id=actor_id,
    )
    return verification
