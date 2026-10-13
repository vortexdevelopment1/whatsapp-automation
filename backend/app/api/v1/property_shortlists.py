import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
from app.models.enums import PropertyShortlistStatus
from app.services.property_shortlist_service import PropertyShortlistService
from app.services.shortlist_config import ShortlistConfig
from app.schemas.property_shortlist import (
    PropertyShortlistResponse,
    PropertyShortlistItemResponse,
    PropertyMatchingDashboardResponse,
    ShortlistReorderRequest,
    ManualShortlistAddRequest,
    Module5HandoffPayload,
)

router = APIRouter(tags=["Property Shortlists & Match Dashboard"])


@router.post(
    "/leads/{lead_id}/property-shortlist/build",
    response_model=PropertyShortlistResponse,
    summary="Build verified property shortlist for lead",
)
def build_shortlist_endpoint(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        shortlist = PropertyShortlistService.build_shortlist(
            db=db,
            lead_id=lead_id,
            created_by="operator@agency.com",
        )
        dashboard = PropertyShortlistService.get_lead_matching_dashboard(db=db, lead_id=lead_id)
        return dashboard.shortlist
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get(
    "/leads/{lead_id}/property-shortlist",
    response_model=Optional[PropertyShortlistResponse],
    summary="Get active property shortlist for lead",
)
def get_lead_shortlist_endpoint(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    dashboard = PropertyShortlistService.get_lead_matching_dashboard(db=db, lead_id=lead_id)
    return dashboard.shortlist


@router.post(
    "/leads/{lead_id}/property-shortlist/refresh",
    response_model=PropertyShortlistResponse,
    summary="Refresh property shortlist verifying latest facts and availability",
)
def refresh_shortlist_endpoint(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        shortlist = PropertyShortlistService.refresh_shortlist(
            db=db,
            lead_id=lead_id,
            user_email="operator@agency.com",
        )
        dashboard = PropertyShortlistService.get_lead_matching_dashboard(db=db, lead_id=lead_id)
        return dashboard.shortlist
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/property-shortlists/{shortlist_id}",
    response_model=PropertyShortlistResponse,
    summary="Get shortlist by ID",
)
def get_shortlist_by_id_endpoint(
    shortlist_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    shortlist = db.query(PropertyShortlist).filter(PropertyShortlist.id == shortlist_id).first()
    if not shortlist:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shortlist not found")
    dashboard = PropertyShortlistService.get_lead_matching_dashboard(db=db, lead_id=shortlist.lead_id)
    return dashboard.shortlist


@router.post(
    "/property-shortlists/{shortlist_id}/items/{match_id}",
    response_model=PropertyShortlistItemResponse,
    summary="Manually add a candidate to the shortlist",
)
def add_shortlist_item_endpoint(
    shortlist_id: uuid.UUID,
    match_id: uuid.UUID,
    body: ManualShortlistAddRequest,
    db: Session = Depends(get_db),
):
    try:
        item = PropertyShortlistService.add_item_to_shortlist(
            db=db,
            shortlist_id=shortlist_id,
            property_match_id=match_id,
            user_email="operator@agency.com",
            manual_override_reason=body.manual_override_reason,
            force_override=body.force_override,
        )
        return item
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete(
    "/property-shortlists/{shortlist_id}/items/{match_id}",
    response_model=PropertyShortlistResponse,
    summary="Remove a candidate from the shortlist",
)
def remove_shortlist_item_endpoint(
    shortlist_id: uuid.UUID,
    match_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        shortlist = PropertyShortlistService.remove_item_from_shortlist(
            db=db,
            shortlist_id=shortlist_id,
            property_match_id=match_id,
            user_email="operator@agency.com",
        )
        dashboard = PropertyShortlistService.get_lead_matching_dashboard(db=db, lead_id=shortlist.lead_id)
        return dashboard.shortlist
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch(
    "/property-shortlists/{shortlist_id}/reorder",
    response_model=PropertyShortlistResponse,
    summary="Reorder items in the shortlist",
)
def reorder_shortlist_endpoint(
    shortlist_id: uuid.UUID,
    body: ShortlistReorderRequest,
    db: Session = Depends(get_db),
):
    try:
        ordered_match_ids = [it.property_match_id for it in body.items]
        shortlist = PropertyShortlistService.reorder_shortlist_items(
            db=db,
            shortlist_id=shortlist_id,
            ordered_match_ids=ordered_match_ids,
            user_email="operator@agency.com",
        )
        dashboard = PropertyShortlistService.get_lead_matching_dashboard(db=db, lead_id=shortlist.lead_id)
        return dashboard.shortlist
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get(
    "/leads/{lead_id}/property-matching/dashboard",
    response_model=PropertyMatchingDashboardResponse,
    summary="Get aggregated property matching dashboard for a lead",
)
def get_property_matching_dashboard_endpoint(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        dashboard = PropertyShortlistService.get_lead_matching_dashboard(db=db, lead_id=lead_id)
        return dashboard
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get(
    "/leads/{lead_id}/property-shortlist/module5-handoff",
    response_model=Module5HandoffPayload,
    summary="Get Module 5 viewing coordination handoff contract",
)
def get_module5_handoff_endpoint(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    try:
        payload = PropertyShortlistService.generate_module5_handoff(db=db, lead_id=lead_id)
        return payload
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
