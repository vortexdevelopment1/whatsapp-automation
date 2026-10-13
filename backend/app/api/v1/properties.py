import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import PropertyType, PropertyStatus, PropertyListingStatus, ListingAvailabilityStatus
from app.schemas.property import (
    PropertyCreate,
    PropertyUpdate,
    PropertyResponse,
)
from app.schemas.property_listing import (
    PropertyListingCreate,
    PropertyListingResponse,
    PropertyDetailResponse,
)
from app.services.property_service import PropertyService
from app.services.property_listing_service import PropertyListingService

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("", response_model=List[PropertyResponse])
def list_properties(
    property_type: Optional[PropertyType] = None,
    country: Optional[str] = None,
    city: Optional[str] = None,
    bedrooms: Optional[int] = None,
    property_status: Optional[PropertyStatus] = Query(None, alias="status"),
    search: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List canonical physical properties with filters and search."""
    service = PropertyService(db)
    properties = service.list_properties(
        property_type=property_type,
        country=country,
        city=city,
        bedrooms=bedrooms,
        property_status=property_status,
        search=search,
        skip=skip,
        limit=limit,
    )
    result = []
    for prop in properties:
        count = service.get_listings_count(prop.id)
        resp = PropertyResponse.model_validate(prop)
        resp.listings_count = count
        result.append(resp)
    return result


@router.post("", response_model=PropertyResponse, status_code=status.HTTP_201_CREATED)
def create_property(
    data: PropertyCreate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Create a new canonical physical property."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyService(db)
    prop = service.create_property(data, actor_id=x_admin_id)
    resp = PropertyResponse.model_validate(prop)
    resp.listings_count = 0
    return resp


@router.get("/{property_id}", response_model=PropertyDetailResponse)
def get_property(
    property_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve full property details including attached source listings."""
    service = PropertyService(db)
    listing_service = PropertyListingService(db)

    prop = service.get_property_or_404(property_id)
    listings = listing_service.list_listings_for_property(property_id)
    formatted_listings = [
        listing_service.format_listing_response(item) for item in listings
    ]

    return PropertyDetailResponse(
        id=prop.id,
        canonical_name=prop.canonical_name,
        building_name=prop.building_name,
        address_line_1=prop.address_line_1,
        address_line_2=prop.address_line_2,
        unit_number=prop.unit_number,
        postal_code=prop.postal_code,
        city=prop.city,
        state_region=prop.state_region,
        district=prop.district,
        country=prop.country,
        latitude=prop.latitude,
        longitude=prop.longitude,
        property_type=prop.property_type,
        bedrooms=prop.bedrooms,
        bathrooms=prop.bathrooms,
        size_sqft=prop.size_sqft,
        furnishing=prop.furnishing,
        status=prop.status,
        listings=formatted_listings,
        listings_count=len(formatted_listings),
        created_at=prop.created_at,
        updated_at=prop.updated_at,
    )


@router.patch("/{property_id}", response_model=PropertyResponse)
def update_property(
    property_id: uuid.UUID,
    data: PropertyUpdate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Update canonical property attributes."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyService(db)
    prop = service.update_property(property_id, data, actor_id=x_admin_id)
    count = service.get_listings_count(prop.id)
    resp = PropertyResponse.model_validate(prop)
    resp.listings_count = count
    return resp


@router.post("/{property_id}/archive", response_model=PropertyResponse)
def archive_property(
    property_id: uuid.UUID,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Archive a property."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyService(db)
    prop = service.archive_property(property_id, actor_id=x_admin_id)
    count = service.get_listings_count(prop.id)
    resp = PropertyResponse.model_validate(prop)
    resp.listings_count = count
    return resp


@router.post("/{property_id}/listings", response_model=PropertyListingResponse, status_code=status.HTTP_201_CREATED)
def create_property_listing(
    property_id: uuid.UUID,
    data: PropertyListingCreate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Attach a new source listing to a canonical property."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyListingService(db)
    listing = service.create_listing(property_id, data, actor_id=x_admin_id)
    return service.format_listing_response(listing)


@router.get("/{property_id}/listings", response_model=List[PropertyListingResponse])
def list_property_listings_for_property(
    property_id: uuid.UUID,
    listing_status: Optional[PropertyListingStatus] = Query(None, alias="status"),
    availability_status: Optional[ListingAvailabilityStatus] = None,
    db: Session = Depends(get_db),
):
    """List all listings for a canonical property."""
    service = PropertyListingService(db)
    listings = service.list_listings_for_property(
        property_id=property_id,
        listing_status=listing_status,
        availability_status=availability_status,
    )
    return [service.format_listing_response(item) for item in listings]
