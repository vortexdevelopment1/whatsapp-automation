import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.property_agent_followup import PropertyAgentFollowUp
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_match import PropertyMatch
from app.schemas.property_agent_followup import (
    PropertyAgentFollowUpResponse,
    ManualFollowUpRequest,
    CancelFollowUpRequest,
    FallbackPreviewResponse,
    ExecuteFallbackRequest,
    ExecuteFallbackResponse,
)
from app.services.property_agent_followup_service import PropertyAgentFollowUpService
from app.services.property_verification_fallback_service import PropertyVerificationFallbackService

router = APIRouter(tags=["Property Agent Follow-up & Fallback"])


@router.get(
    "/property-agent-followups",
    response_model=List[PropertyAgentFollowUpResponse],
    summary="List follow-up SLA tasks",
)
def list_followups(
    lead_id: Optional[uuid.UUID] = Query(None),
    match_id: Optional[uuid.UUID] = Query(None),
    outreach_id: Optional[uuid.UUID] = Query(None),
    status: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(PropertyAgentFollowUp)
    if lead_id:
        query = query.filter(PropertyAgentFollowUp.lead_id == lead_id)
    if match_id:
        query = query.filter(PropertyAgentFollowUp.property_match_id == match_id)
    if outreach_id:
        query = query.filter(PropertyAgentFollowUp.outreach_id == outreach_id)
    if status:
        query = query.filter(PropertyAgentFollowUp.status == status)
    return query.order_by(PropertyAgentFollowUp.due_at.asc()).limit(limit).all()


@router.get(
    "/property-agent-followups/{id}",
    response_model=PropertyAgentFollowUpResponse,
    summary="Get follow-up SLA task by ID",
)
def get_followup(
    id: uuid.UUID,
    db: Session = Depends(get_db),
):
    followup = db.query(PropertyAgentFollowUp).filter(PropertyAgentFollowUp.id == id).first()
    if not followup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Follow-up task '{id}' not found.")
    return followup


@router.get(
    "/property-matches/{match_id}/followups",
    response_model=List[PropertyAgentFollowUpResponse],
    summary="Get all follow-up tasks for a property match",
)
def get_match_followups(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    return (
        db.query(PropertyAgentFollowUp)
        .filter(PropertyAgentFollowUp.property_match_id == match_id)
        .order_by(PropertyAgentFollowUp.created_at.desc())
        .all()
    )


@router.post(
    "/property-agent-outreach/{outreach_id}/follow-up",
    response_model=PropertyAgentFollowUpResponse,
    summary="Send manual follow-up now",
)
def send_manual_followup(
    outreach_id: uuid.UUID,
    payload: Optional[ManualFollowUpRequest] = None,
    db: Session = Depends(get_db),
):
    followup_svc = PropertyAgentFollowUpService(db)
    reason = payload.reason if payload else None
    return followup_svc.send_manual_followup(
        outreach_id=outreach_id,
        reason=reason,
        actor_id="operator",
    )


@router.post(
    "/property-agent-followups/{id}/cancel",
    response_model=PropertyAgentFollowUpResponse,
    summary="Cancel a scheduled follow-up task",
)
def cancel_followup(
    id: uuid.UUID,
    payload: Optional[CancelFollowUpRequest] = None,
    db: Session = Depends(get_db),
):
    followup_svc = PropertyAgentFollowUpService(db)
    reason = payload.reason if payload and payload.reason else "Operator cancelled"
    return followup_svc.cancel_followup(
        followup_id=id,
        reason=reason,
        actor_id="operator",
    )


@router.get(
    "/property-matches/{match_id}/fallback-preview",
    response_model=FallbackPreviewResponse,
    summary="Preview fallback options when agent is unresponsive or listing is unavailable",
)
def preview_fallback(
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    fallback_svc = PropertyVerificationFallbackService(db)
    return fallback_svc.preview_fallback(match_id=match_id)


@router.post(
    "/property-matches/{match_id}/execute-fallback",
    response_model=ExecuteFallbackResponse,
    summary="Execute fallback strategy (alternate listing, next property candidate, or human review)",
)
def execute_fallback(
    match_id: uuid.UUID,
    payload: Optional[ExecuteFallbackRequest] = None,
    db: Session = Depends(get_db),
):
    fallback_svc = PropertyVerificationFallbackService(db)
    reason = payload.reason if payload else None
    return fallback_svc.execute_fallback(
        match_id=match_id,
        actor_id="operator",
        reason=reason,
    )


@router.post(
    "/property-agent-followups/process-due",
    summary="Batch execute all due follow-up tasks",
)
def process_due_followups(
    db: Session = Depends(get_db),
):
    followup_svc = PropertyAgentFollowUpService(db)
    results = followup_svc.process_due_followups(actor_id="batch_worker")
    return {"status": "COMPLETED", "processed_count": len(results), "results": results}
