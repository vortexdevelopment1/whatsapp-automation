import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.viewing import Viewing
from app.models.enums import ViewingStatus
from app.schemas.viewing import (
    ViewingCreateRequest,
    ViewingUpdateRequest,
    ViewingTransitionRequest,
    ViewingCancelRequest,
    ViewingCompleteRequest,
    ViewingNoShowRequest,
    ViewingSlotCreateRequest,
    ViewingSlotUpdateRequest,
    ViewingSlotResponse,
    ViewingResponse,
    ViewingDetailResponse,
    ViewingListResponse,
    ViewingPropertySummary,
    ViewingListingSummary,
    ViewingAgentSummary,
)
from app.schemas.viewing_reminder import (
    ViewingReminderResponse,
    ViewingScheduleHistoryResponse,
    ViewingRescheduleApiRequest,
    ViewingReminderBatchProcessResponse,
)
from app.services.viewing_service import ViewingService
from app.services.viewing_slot_service import ViewingSlotService
from app.services.viewing_reminder_service import ViewingReminderService
from app.services.viewing_reschedule_service import ViewingRescheduleService
from app.services.viewing_cancellation_service import ViewingCancellationService

router = APIRouter()


def _to_viewing_response(v: Viewing) -> ViewingResponse:
    p_summary = None
    if v.property:
        p_summary = ViewingPropertySummary(
            property_id=v.property.id,
            canonical_name=v.property.canonical_name,
            building_name=v.property.building_name,
            address=v.property.address_normalized or v.property.address_line_1,
            district=v.property.district,
            property_type=v.property.property_type.value if hasattr(v.property.property_type, "value") else str(v.property.property_type),
            bedrooms=v.property.bedrooms,
        )

    l_summary = None
    if v.listing:
        l_summary = ViewingListingSummary(
            listing_id=v.listing.id,
            asking_price=float(v.listing.asking_price) if v.listing.asking_price is not None else None,
            currency=v.listing.currency or "SGD",
            available_from=str(v.listing.available_from) if v.listing.available_from else None,
            lease_min_months=v.listing.lease_min_months,
        )

    a_summary = None
    if v.property_agent:
        a_summary = ViewingAgentSummary(
            agent_id=v.property_agent.id,
            full_name=v.property_agent.full_name,
            agency_name=v.property_agent.agency_name,
            phone=v.property_agent.phone,
        )

    lead_name = None
    if v.lead:
        lead_name = v.lead.full_name or v.lead.phone

    return ViewingResponse(
        id=v.id,
        lead_id=v.lead_id,
        shortlist_id=v.shortlist_id,
        shortlist_item_id=v.shortlist_item_id,
        property_match_id=v.property_match_id,
        property_id=v.property_id,
        listing_id=v.listing_id,
        property_agent_id=v.property_agent_id,
        status=v.status,
        scheduled_start_at=v.scheduled_start_at,
        scheduled_end_at=v.scheduled_end_at,
        timezone=v.timezone,
        duration_minutes=v.duration_minutes,
        location_type=v.location_type,
        location_text=v.location_text,
        meeting_url=v.meeting_url,
        tenant_confirmation_status=v.tenant_confirmation_status,
        agent_confirmation_status=v.agent_confirmation_status,
        schedule_version=v.schedule_version or 1,
        reschedule_count=v.reschedule_count,
        previous_scheduled_start_at=v.previous_scheduled_start_at,
        previous_scheduled_end_at=v.previous_scheduled_end_at,
        reschedule_reason=v.reschedule_reason,
        cancellation_reason=v.cancellation_reason,
        cancelled_by=v.cancelled_by,
        cancelled_at=v.cancelled_at,
        completed_at=v.completed_at,
        outcome=v.outcome,
        outcome_notes=v.outcome_notes,
        created_by=v.created_by,
        created_at=v.created_at,
        updated_at=v.updated_at,
        property_summary=p_summary,
        listing_summary=l_summary,
        agent_summary=a_summary,
        lead_name=lead_name,
    )


def _to_viewing_detail_response(v: Viewing) -> ViewingDetailResponse:
    base = _to_viewing_response(v)
    slots_resp = [ViewingSlotResponse.model_validate(s) for s in v.slots]
    events_resp = [
        {
            "id": e.id,
            "viewing_id": e.viewing_id,
            "event_type": e.event_type,
            "old_status": e.old_status,
            "new_status": e.new_status,
            "actor_type": e.actor_type,
            "actor_id": e.actor_id,
            "metadata": e.event_metadata,
            "created_at": e.created_at,
        }
        for e in v.events
    ]
    return ViewingDetailResponse(
        **base.model_dump(),
        slots=slots_resp,
        events=events_resp,
    )


# 1. Create viewing from match
@router.post(
    "/property-matches/{match_id}/viewings",
    response_model=ViewingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create viewing workflow for a property match candidate",
)
def create_viewing_from_match(
    match_id: uuid.UUID,
    payload: Optional[ViewingCreateRequest] = None,
    db: Session = Depends(get_db),
):
    try:
        duration = payload.duration_minutes if payload else None
        tz = payload.timezone if payload else None
        loc_type = payload.location_type if payload else None
        loc_text = payload.location_text if payload else None
        meeting_url = payload.meeting_url if payload else None
        created_by = payload.created_by if payload and payload.created_by else "operator"

        viewing = ViewingService.create_viewing_from_match(
            db=db,
            match_id=match_id,
            created_by=created_by,
            duration_minutes=duration,
            timezone=tz,
            location_type=loc_type,
            location_text=loc_text,
            meeting_url=meeting_url,
        )
        return _to_viewing_response(viewing)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# 2. List viewings for a lead
@router.get(
    "/leads/{lead_id}/viewings",
    response_model=ViewingListResponse,
    summary="List all viewings for a specific tenant lead",
)
def list_lead_viewings(
    lead_id: uuid.UUID,
    status: Optional[ViewingStatus] = None,
    db: Session = Depends(get_db),
):
    items = ViewingService.list_viewings(db=db, lead_id=lead_id, status=status)
    return ViewingListResponse(
        total=len(items),
        items=[_to_viewing_response(v) for v in items],
    )


# 3. Global list of viewings
@router.get(
    "/viewings",
    response_model=ViewingListResponse,
    summary="List viewings with filters",
)
def list_viewings(
    lead_id: Optional[uuid.UUID] = None,
    status: Optional[ViewingStatus] = None,
    property_id: Optional[uuid.UUID] = None,
    property_agent_id: Optional[uuid.UUID] = None,
    upcoming_only: bool = False,
    db: Session = Depends(get_db),
):
    items = ViewingService.list_viewings(
        db=db,
        lead_id=lead_id,
        status=status,
        property_id=property_id,
        property_agent_id=property_agent_id,
        upcoming_only=upcoming_only,
    )
    return ViewingListResponse(
        total=len(items),
        items=[_to_viewing_response(v) for v in items],
    )


# 4. Viewing detail
@router.get(
    "/viewings/{viewing_id}",
    response_model=ViewingDetailResponse,
    summary="Get full viewing details including slots and events",
)
def get_viewing_detail(
    viewing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        viewing = ViewingService.get_viewing(db=db, viewing_id=viewing_id)
        return _to_viewing_detail_response(viewing)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# 5. Update metadata
@router.patch(
    "/viewings/{viewing_id}",
    response_model=ViewingResponse,
    summary="Update viewing safe metadata",
)
def update_viewing_metadata(
    viewing_id: uuid.UUID,
    payload: ViewingUpdateRequest,
    db: Session = Depends(get_db),
):
    try:
        updated = ViewingService.update_viewing_metadata(
            db=db,
            viewing_id=viewing_id,
            duration_minutes=payload.duration_minutes,
            timezone=payload.timezone,
            location_type=payload.location_type,
            location_text=payload.location_text,
            meeting_url=payload.meeting_url,
            outcome_notes=payload.outcome_notes,
        )
        return _to_viewing_response(updated)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# 6. Slots - Add
@router.post(
    "/viewings/{viewing_id}/slots",
    response_model=ViewingSlotResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add an available viewing slot",
)
def add_viewing_slot(
    viewing_id: uuid.UUID,
    payload: ViewingSlotCreateRequest,
    db: Session = Depends(get_db),
):
    try:
        slot = ViewingSlotService.add_slot(
            db=db,
            viewing_id=viewing_id,
            start_at=payload.start_at,
            end_at=payload.end_at,
            source=payload.source,
            timezone=payload.timezone,
            source_message_id=payload.source_message_id,
        )
        return ViewingSlotResponse.model_validate(slot)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# 7. Slots - Select
@router.post(
    "/viewings/{viewing_id}/slots/{slot_id}/select",
    response_model=ViewingSlotResponse,
    summary="Select a specific slot for the viewing",
)
def select_viewing_slot(
    viewing_id: uuid.UUID,
    slot_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        slot = ViewingSlotService.select_slot(
            db=db,
            viewing_id=viewing_id,
            slot_id=slot_id,
        )
        return ViewingSlotResponse.model_validate(slot)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# 8. Workflow transition
@router.post(
    "/viewings/{viewing_id}/transition",
    response_model=ViewingResponse,
    summary="Transition viewing state according to workflow rules",
)
def transition_viewing_state(
    viewing_id: uuid.UUID,
    payload: ViewingTransitionRequest,
    db: Session = Depends(get_db),
):
    try:
        viewing = ViewingService.transition_viewing(
            db=db,
            viewing_id=viewing_id,
            target_status=payload.target_status,
            reason=payload.reason,
            actor_type=payload.actor_type,
            actor_id=payload.actor_id or "operator",
        )
        return _to_viewing_response(viewing)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# 9. Cancel viewing
@router.post(
    "/viewings/{viewing_id}/cancel",
    response_model=ViewingResponse,
    summary="Cancel viewing with reason code and notifications",
)
def cancel_viewing(
    viewing_id: uuid.UUID,
    payload: ViewingCancelRequest,
    db: Session = Depends(get_db),
):
    try:
        service = ViewingCancellationService(db)
        viewing = service.cancel_viewing(
            viewing_id=viewing_id,
            cancelling_party=payload.cancelled_by or "OPERATOR",
            reason_code=payload.reason_code or "OPERATOR_ACTION",
            reason_text=payload.reason,
            actor_id=payload.cancelled_by or "operator",
        )
        return _to_viewing_response(viewing)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# 9b. Reschedule viewing (Module 5 Phase 6)
@router.post(
    "/viewings/{viewing_id}/reschedule",
    response_model=ViewingResponse,
    summary="Request viewing reschedule and safely re-open scheduling workflow",
)
def reschedule_viewing(
    viewing_id: uuid.UUID,
    payload: ViewingRescheduleApiRequest,
    db: Session = Depends(get_db),
):
    try:
        service = ViewingRescheduleService(db)
        viewing = service.request_reschedule(
            viewing_id=viewing_id,
            requested_by=payload.requested_by,
            reason=payload.reason,
            candidate_slot_start=payload.candidate_slot_start,
            candidate_slot_end=payload.candidate_slot_end,
            actor_id=payload.requested_by.lower() if payload.requested_by else "operator",
        )
        return _to_viewing_response(viewing)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# 9c. Schedule history (Module 5 Phase 6)
@router.get(
    "/viewings/{viewing_id}/schedule-history",
    response_model=List[ViewingScheduleHistoryResponse],
    summary="Retrieve full booking schedule version history for a viewing",
)
def get_viewing_schedule_history(
    viewing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = ViewingRescheduleService(db)
    return service.get_schedule_history(viewing_id)


# 9d. Viewing Reminders (Module 5 Phase 6)
@router.get(
    "/viewings/{viewing_id}/reminders",
    response_model=List[ViewingReminderResponse],
    summary="List operational reminders scheduled for a viewing",
)
def list_viewing_reminders(
    viewing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = ViewingReminderService(db)
    return service.list_reminders_for_viewing(viewing_id)


@router.post(
    "/viewings/{viewing_id}/reminders/rebuild",
    response_model=List[ViewingReminderResponse],
    summary="Rebuild operational reminders for a viewing",
)
def rebuild_viewing_reminders(
    viewing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        service = ViewingReminderService(db)
        return service.rebuild_reminders(viewing_id=viewing_id, actor_id="operator")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/viewings/reminders/process-due",
    response_model=ViewingReminderBatchProcessResponse,
    summary="Process and dispatch all due viewing reminders batch",
)
def process_due_viewing_reminders(
    db: Session = Depends(get_db),
):
    service = ViewingReminderService(db)
    results = service.process_due_reminders(actor_id="scheduler")
    return ViewingReminderBatchProcessResponse(
        total_processed=len(results),
        results=results,
    )


# 10. Complete viewing
@router.post(
    "/viewings/{viewing_id}/complete",
    response_model=ViewingResponse,
    summary="Mark viewing as completed",
)
def complete_viewing(
    viewing_id: uuid.UUID,
    payload: Optional[ViewingCompleteRequest] = None,
    db: Session = Depends(get_db),
):
    try:
        notes = payload.notes if payload else None
        viewing = ViewingService.complete_viewing(
            db=db,
            viewing_id=viewing_id,
            notes=notes,
        )
        return _to_viewing_response(viewing)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# 11. No-show viewing
@router.post(
    "/viewings/{viewing_id}/no-show",
    response_model=ViewingResponse,
    summary="Record viewing no-show",
)
def record_no_show_viewing(
    viewing_id: uuid.UUID,
    payload: Optional[ViewingNoShowRequest] = None,
    db: Session = Depends(get_db),
):
    try:
        actor = payload.actor if payload else "TENANT"
        notes = payload.notes if payload else None
        viewing = ViewingService.record_no_show(
            db=db,
            viewing_id=viewing_id,
            actor=actor,
            notes=notes,
        )
        return _to_viewing_response(viewing)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
