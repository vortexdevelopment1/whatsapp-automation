import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import ConfirmationParty
from app.schemas.viewing_confirmation import (
    ViewingConfirmationRequestCreate,
    ViewingConfirmationRequestResponse,
    ViewingConfirmationStatusOverview,
    ViewingManualConfirmationRequest,
    ViewingDeclineRequest,
    ViewingFinalizeBookingResponse,
)
from app.services.viewing_confirmation_service import ViewingConfirmationService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["viewing-confirmation"])


@router.post(
    "/viewings/{viewing_id}/confirmation/tenant/request",
    response_model=ViewingConfirmationRequestResponse,
    summary="Request final viewing confirmation from the tenant",
)
def request_tenant_confirmation(
    viewing_id: uuid.UUID,
    payload: ViewingConfirmationRequestCreate,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        return service.request_tenant_confirmation(
            viewing_id=viewing_id,
            actor_id=payload.actor_id or "operator",
            custom_message=payload.custom_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/confirmation/agent/request",
    response_model=ViewingConfirmationRequestResponse,
    summary="Request final viewing confirmation from the listing/property agent",
)
def request_agent_confirmation(
    viewing_id: uuid.UUID,
    payload: ViewingConfirmationRequestCreate,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        return service.request_agent_confirmation(
            viewing_id=viewing_id,
            actor_id=payload.actor_id or "operator",
            custom_message=payload.custom_message,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/confirmation/tenant/confirm",
    response_model=ViewingConfirmationStatusOverview,
    summary="Record manual confirmation on behalf of the tenant",
)
def confirm_tenant(
    viewing_id: uuid.UUID,
    payload: ViewingManualConfirmationRequest,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        return service.manual_confirm(
            viewing_id=viewing_id,
            party=ConfirmationParty.TENANT,
            actor_id=payload.actor_id or "operator",
            reason=payload.reason,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/confirmation/agent/confirm",
    response_model=ViewingConfirmationStatusOverview,
    summary="Record manual confirmation on behalf of the property agent",
)
def confirm_agent(
    viewing_id: uuid.UUID,
    payload: ViewingManualConfirmationRequest,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        return service.manual_confirm(
            viewing_id=viewing_id,
            party=ConfirmationParty.PROPERTY_AGENT,
            actor_id=payload.actor_id or "operator",
            reason=payload.reason,
            notes=payload.notes,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/confirmation/tenant/decline",
    response_model=ViewingConfirmationStatusOverview,
    summary="Record manual decline on behalf of the tenant",
)
def decline_tenant(
    viewing_id: uuid.UUID,
    payload: ViewingDeclineRequest,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        return service.manual_decline(
            viewing_id=viewing_id,
            party=ConfirmationParty.TENANT,
            actor_id=payload.actor_id or "operator",
            reason=payload.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/confirmation/agent/decline",
    response_model=ViewingConfirmationStatusOverview,
    summary="Record manual decline on behalf of the property agent",
)
def decline_agent(
    viewing_id: uuid.UUID,
    payload: ViewingDeclineRequest,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        return service.manual_decline(
            viewing_id=viewing_id,
            party=ConfirmationParty.PROPERTY_AGENT,
            actor_id=payload.actor_id or "operator",
            reason=payload.reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/viewings/{viewing_id}/finalize-booking",
    response_model=ViewingFinalizeBookingResponse,
    summary="Transactionally finalize booking and mark viewing CONFIRMED",
)
def finalize_booking(
    viewing_id: uuid.UUID,
    payload: Optional[ViewingManualConfirmationRequest] = None,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        actor_id = payload.actor_id if payload else "operator"
        reason = payload.reason if payload else "Both parties confirmed viewing slot"
        return service.finalize_booking(
            viewing_id=viewing_id,
            actor_id=actor_id,
            reason=reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/viewings/{viewing_id}/confirmation-status",
    response_model=ViewingConfirmationStatusOverview,
    summary="Get current viewing confirmation and booking status overview",
)
def get_confirmation_status(
    viewing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = ViewingConfirmationService(db)
    try:
        return service.get_confirmation_status_overview(viewing_id=viewing_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
