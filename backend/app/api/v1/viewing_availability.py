import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.viewing import Viewing
from app.models.message import WhatsAppMessage
from app.models.audit_log import AuditLog
from app.models.enums import MessageDirection
from app.schemas.viewing_availability import (
    ViewingAgentAvailabilityRequestCreate,
    ViewingAvailabilityRequestResponse,
    ViewingAgentAvailabilityStatusResponse,
    ViewingMessageAnalysisRequest,
    AgentMessageManualCorrelationRequest,
    TenantViewingAvailabilityRequestCreate,
    TenantViewingAvailabilityRequestResponse,
    TenantAvailabilityUnderstandingResult,
    MutualSlotMatchItem,
    ViewingSlotMatchingResult,
    ViewingTenantAvailabilityStatusResponse,
    CandidateSlotProposeRequest,
    ManualTenantAvailabilityCreate,
    TenantAvailabilityMatchRequest,
)
from app.schemas.viewing import ViewingSlotResponse
from app.models.viewing import ViewingSlot
from app.models.enums import ViewingSlotSource, ViewingSlotStatus
from app.services.viewing_agent_availability_service import ViewingAgentAvailabilityService
from app.services.viewing_availability_understanding_service import ViewingAvailabilityUnderstandingService
from app.services.tenant_viewing_availability_service import TenantViewingAvailabilityService
from app.services.tenant_viewing_availability_understanding_service import TenantViewingAvailabilityUnderstandingService
from app.services.viewing_slot_matching_service import ViewingSlotMatchingService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/viewings/{viewing_id}/agent-availability/request",
    response_model=ViewingAvailabilityRequestResponse,
    summary="Request viewing availability from the listing/property agent",
)
def request_agent_availability(
    viewing_id: uuid.UUID,
    payload: ViewingAgentAvailabilityRequestCreate,
    db: Session = Depends(get_db),
):
    """
    Step 36: Request viewing availability from listing agent.
    - Validates viewing, candidate match, active property and listing, tenant qualification.
    - Resolves/reuses PropertyAgentConversation.
    - Creates ViewingAvailabilityRequest with idempotency key.
    - Sends privacy-preserving message via existing WhatsAppService.
    - Updates viewing status to AWAITING_AGENT_AVAILABILITY.
    """
    service = ViewingAgentAvailabilityService(db)
    try:
        req = service.request_agent_availability(
            viewing_id=viewing_id,
            actor_id=payload.actor_id or "operator",
            custom_message=payload.custom_message,
            tenant_broad_availability=payload.tenant_broad_availability,
        )
        return req
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error requesting agent availability: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/viewings/{viewing_id}/agent-availability",
    response_model=ViewingAgentAvailabilityStatusResponse,
    summary="Get current viewing availability request status and agent slots",
)
def get_viewing_availability_status(
    viewing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Step 37: Retrieve request status, message status, agent, last response, and candidate slots.
    """
    service = ViewingAgentAvailabilityService(db)
    try:
        result = service.get_viewing_availability_status(viewing_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching viewing availability status: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/viewing-agent-messages/{message_id}/analyze",
    summary="Analyze inbound property agent message for viewing slots",
)
async def analyze_viewing_agent_message(
    message_id: uuid.UUID,
    payload: Optional[ViewingMessageAnalysisRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Step 38: Analyze inbound property-agent message and extract available slots.
    """
    actor_id = payload.actor_id if payload else "operator"
    override_viewing_id = payload.override_viewing_id if payload else None

    understanding_service = ViewingAvailabilityUnderstandingService(db)
    try:
        result = await understanding_service.process_inbound_agent_message(
            message_id=message_id,
            override_viewing_id=override_viewing_id,
            actor_id=actor_id,
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error analyzing viewing agent message: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/viewing-agent-messages/{message_id}/resolve-viewing",
    summary="Manually correlate an ambiguous property agent message to a viewing",
)
async def manually_correlate_message_to_viewing(
    message_id: uuid.UUID,
    payload: AgentMessageManualCorrelationRequest,
    db: Session = Depends(get_db),
):
    """
    Step 39 & 30: Manually correlate an ambiguous agent message to a specific viewing,
    audit the action, and safely reprocess slot extraction.
    """
    msg = db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Message {message_id} not found")

    viewing = db.query(Viewing).filter(Viewing.id == payload.viewing_id).first()
    if not viewing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Viewing {payload.viewing_id} not found")

    # Record AuditLog for manual correlation
    audit = AuditLog(
        action="MANUAL_CORRELATION_RESOLVED",
        actor_id=payload.actor_id or "operator",
        entity_type="viewing",
        entity_id=str(payload.viewing_id),
        new_value={
            "message_id": str(message_id),
            "reason": payload.reason,
        },
    )
    db.add(audit)
    db.commit()

    understanding_service = ViewingAvailabilityUnderstandingService(db)
    try:
        result = await understanding_service.process_inbound_agent_message(
            message_id=message_id,
            override_viewing_id=payload.viewing_id,
            actor_id=payload.actor_id or "operator",
        )
        return {
            "status": "MANUAL_CORRELATION_SUCCESS",
            "message_id": str(message_id),
            "viewing_id": str(payload.viewing_id),
            "reason": payload.reason,
            "processing_result": result,
        }
    except Exception as e:
        logger.error(f"Error reprocessing manual correlation: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# ==============================================================================
# MODULE 5 PHASE 4: TENANT AVAILABILITY & SLOT MATCHING ENDPOINTS
# ==============================================================================

@router.post(
    "/viewings/{viewing_id}/tenant-availability/request",
    response_model=TenantViewingAvailabilityRequestResponse,
    summary="Send viewing availability options or inquiry to tenant via WhatsApp",
)
def request_tenant_availability(
    viewing_id: uuid.UUID,
    payload: Optional[TenantViewingAvailabilityRequestCreate] = None,
    db: Session = Depends(get_db),
):
    """
    Step 44: Request tenant availability.
    - Validates viewing active, agent slots available, property/listing active, tenant eligible.
    - Sends WhatsApp message offering slots or inquiring general availability.
    - Tracks idempotency key viewing:{viewing_id}:tenant-availability-request:{version}.
    - Transitions viewing to AWAITING_TENANT_AVAILABILITY.
    """
    service = TenantViewingAvailabilityService(db)
    actor_id = payload.actor_id if payload and payload.actor_id else "operator"
    try:
        result = service.request_tenant_availability(
            viewing_id=viewing_id,
            payload=payload,
            actor_id=actor_id,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error requesting tenant availability: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/viewings/{viewing_id}/tenant-availability",
    response_model=ViewingTenantAvailabilityStatusResponse,
    summary="Get tenant availability, agent slots, mutual overlaps, and current proposed slot",
)
def get_tenant_availability_status(
    viewing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Step 45: Returns comprehensive slot overview:
    - Agent slots
    - Tenant slots / windows
    - Computed mutual matches
    - Current proposed slot
    """
    viewing = db.query(Viewing).filter(Viewing.id == viewing_id).first()
    if not viewing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Viewing {viewing_id} not found")

    slots = (
        db.query(ViewingSlot)
        .filter(ViewingSlot.viewing_id == viewing_id)
        .order_by(ViewingSlot.start_at.asc())
        .all()
    )

    agent_slots = [ViewingSlotResponse.from_orm(s) for s in slots if s.source == ViewingSlotSource.PROPERTY_AGENT]
    tenant_slots = [ViewingSlotResponse.from_orm(s) for s in slots if s.source in [ViewingSlotSource.TENANT, ViewingSlotSource.HUMAN_OPERATOR]]

    # Run deterministic matching to get current mutual slots
    matching_service = ViewingSlotMatchingService(db)
    # Convert tenant slots to windows if any
    tenant_windows = []
    for ts in tenant_slots:
        tenant_windows.append(
            TenantAvailabilityWindowItem(
                start_at=ts.start_at,
                end_at=ts.end_at or ts.start_at,
                timezone=ts.timezone,
                confidence=1.0,
            )
        )

    match_result = matching_service.match_slots(
        viewing_id=viewing_id,
        tenant_windows=tenant_windows if tenant_windows else None,
    )

    proposed_slot = next((ViewingSlotResponse.from_orm(s) for s in slots if s.status == ViewingSlotStatus.PROPOSED), None)
    if not proposed_slot:
        proposed_slot = next((ViewingSlotResponse.from_orm(s) for s in slots if s.status == ViewingSlotStatus.SELECTED), None)

    return ViewingTenantAvailabilityStatusResponse(
        viewing_id=viewing.id,
        viewing_status=viewing.status.value,
        agent_slots=agent_slots,
        tenant_slots=tenant_slots,
        mutual_slots=match_result.mutual_slots,
        current_proposed_slot=proposed_slot,
        needs_human_review=(viewing.status.value == "NEEDS_HUMAN_REVIEW"),
    )


@router.post(
    "/viewings/{viewing_id}/match-slots",
    response_model=ViewingSlotMatchingResult,
    summary="Compute deterministic mutual viewing slots between agent and tenant availability",
)
def match_viewing_slots(
    viewing_id: uuid.UUID,
    payload: Optional[TenantAvailabilityMatchRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Step 46: Deterministically calculate mutual candidate viewing slots without LLM.
    """
    matching_service = ViewingSlotMatchingService(db)
    try:
        result = matching_service.match_slots(
            viewing_id=viewing_id,
            tenant_windows=payload.tenant_windows if payload else None,
            selected_slot_id=payload.selected_slot_id if payload else None,
            duration_minutes=payload.duration_minutes if payload else None,
            interval_minutes=payload.interval_minutes if payload else None,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error matching viewing slots: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/slots/{slot_id}/propose",
    response_model=ViewingSlotResponse,
    summary="Propose a candidate viewing slot (transitions viewing to SLOT_PROPOSED, NOT CONFIRMED)",
)
def propose_candidate_slot(
    viewing_id: uuid.UUID,
    slot_id: uuid.UUID,
    payload: Optional[CandidateSlotProposeRequest] = None,
    db: Session = Depends(get_db),
):
    """
    Step 47: Propose candidate viewing slot.
    - Moves viewing to SLOT_PROPOSED.
    - Revalidates property, listing, and agent slot validity.
    - Enforces double-selection protection.
    - CRITICAL: Does NOT confirm viewing.
    """
    viewing = db.query(Viewing).filter(Viewing.id == viewing_id).first()
    if not viewing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Viewing {viewing_id} not found")

    slot = db.query(ViewingSlot).filter(ViewingSlot.id == slot_id, ViewingSlot.viewing_id == viewing_id).first()
    if not slot:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ViewingSlot {slot_id} not found for viewing {viewing_id}")

    understanding_service = TenantViewingAvailabilityUnderstandingService(db)
    actor_id = payload.actor_id if payload and payload.actor_id else "operator"
    reason = payload.reason if payload and payload.reason else "Candidate viewing slot proposed by operator."

    try:
        proposed_slot = understanding_service.propose_candidate_slot(
            viewing=viewing,
            candidate_slot=slot,
            actor_id=actor_id,
            reason=reason,
        )
        return ViewingSlotResponse.from_orm(proposed_slot)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error proposing slot: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/tenant-availability/manual",
    summary="Record tenant availability obtained manually (e.g. phone call or external discussion)",
)
def record_manual_tenant_availability(
    viewing_id: uuid.UUID,
    payload: ManualTenantAvailabilityCreate,
    db: Session = Depends(get_db),
):
    """
    Step 43: Record manual tenant availability with source = HUMAN_OPERATOR.
    """
    viewing = db.query(Viewing).filter(Viewing.id == viewing_id).first()
    if not viewing:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Viewing {viewing_id} not found")

    actor_id = payload.actor_id or "operator"
    created_slots = []
    for w in payload.windows:
        w_start_utc = ViewingSlotMatchingService.to_utc(w.start_at, w.timezone)
        w_end_utc = ViewingSlotMatchingService.to_utc(w.end_at, w.timezone)
        slot = ViewingSlot(
            viewing_id=viewing.id,
            source=ViewingSlotSource.HUMAN_OPERATOR,
            start_at=w_start_utc,
            end_at=w_end_utc,
            timezone=w.timezone,
            status=ViewingSlotStatus.AVAILABLE,
        )
        db.add(slot)
        created_slots.append(slot)
    db.commit()

    # Audit log
    audit = AuditLog(
        action="MANUAL_TENANT_AVAILABILITY_RECORDED",
        actor_id=actor_id,
        entity_type="viewing",
        entity_id=str(viewing.id),
        new_value={
            "windows_count": len(payload.windows),
            "notes": payload.notes,
        },
    )
    db.add(audit)
    db.commit()

    return {
        "status": "MANUAL_AVAILABILITY_RECORDED",
        "viewing_id": str(viewing.id),
        "windows_count": len(created_slots),
        "slots": [ViewingSlotResponse.from_orm(s) for s in created_slots],
    }


@router.post(
    "/tenant-viewing-messages/{message_id}/analyze",
    response_model=TenantAvailabilityUnderstandingResult,
    summary="Analyze inbound tenant message for viewing scheduling, slot selection, or availability",
)
async def analyze_tenant_viewing_message(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Step 7 & 38: Analyze inbound tenant message:
    - Resolves viewing correlation safely.
    - Classifies intent.
    - Extracts availability windows or slot choice.
    - Runs matching and proposes candidate slot if matched.
    """
    understanding_service = TenantViewingAvailabilityUnderstandingService(db)
    try:
        result = await understanding_service.process_inbound_tenant_message(
            message_id=message_id,
            actor_id="tenant",
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.error(f"Error analyzing tenant viewing message: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

