import uuid
from datetime import date, datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import PropertyListingStatus, ListingAvailabilityStatus
from app.schemas.property_listing import (
    PropertyListingUpdate,
    PropertyListingResponse,
)
from app.services.property_listing_service import PropertyListingService

router = APIRouter(prefix="/property-listings", tags=["property-listings"])


class AvailabilityUpdatePayload(BaseModel):
    availability_status: ListingAvailabilityStatus
    available_from: Optional[date] = None
    last_verified_at: Optional[datetime] = None


@router.get("", response_model=List[PropertyListingResponse])
def list_property_listings(
    property_id: Optional[uuid.UUID] = None,
    source_id: Optional[uuid.UUID] = None,
    agent_id: Optional[uuid.UUID] = None,
    listing_status: Optional[PropertyListingStatus] = Query(None, alias="status"),
    availability_status: Optional[ListingAvailabilityStatus] = None,
    currency: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Query listings across properties with filtering."""
    service = PropertyListingService(db)
    listings = service.list_listings(
        property_id=property_id,
        source_id=source_id,
        agent_id=agent_id,
        listing_status=listing_status,
        availability_status=availability_status,
        currency=currency,
        skip=skip,
        limit=limit,
    )
    return [service.format_listing_response(item) for item in listings]


@router.get("/{listing_id}", response_model=PropertyListingResponse)
def get_property_listing(
    listing_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve details of a single property listing."""
    service = PropertyListingService(db)
    listing = service.get_listing_or_404(listing_id)
    return service.format_listing_response(listing)


@router.patch("/{listing_id}", response_model=PropertyListingResponse)
def update_property_listing(
    listing_id: uuid.UUID,
    data: PropertyListingUpdate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Update listing details, pricing, lease terms, or metadata."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyListingService(db)
    listing = service.update_listing(listing_id, data, actor_id=x_admin_id)
    return service.format_listing_response(listing)


@router.post("/{listing_id}/archive", response_model=PropertyListingResponse)
def archive_property_listing(
    listing_id: uuid.UUID,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Archive a property listing."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyListingService(db)
    listing = service.archive_listing(listing_id, actor_id=x_admin_id)
    return service.format_listing_response(listing)


@router.patch("/{listing_id}/availability", response_model=PropertyListingResponse)
def update_listing_availability(
    listing_id: uuid.UUID,
    payload: AvailabilityUpdatePayload,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Explicitly update listing availability state and verification timestamp."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyListingService(db)
    listing = service.update_availability(
        listing_id,
        availability_status=payload.availability_status,
        available_from=payload.available_from,
        last_verified_at=payload.last_verified_at,
        actor_id=x_admin_id,
    )
    return service.format_listing_response(listing)
