import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import PropertySourceType, PropertySourceStatus
from app.schemas.property_source import (
    PropertySourceCreate,
    PropertySourceUpdate,
    PropertySourceResponse,
)
from app.services.property_source_service import PropertySourceService

router = APIRouter(prefix="/property-sources", tags=["property-sources"])


@router.get("", response_model=List[PropertySourceResponse])
def list_property_sources(
    source_type: Optional[PropertySourceType] = None,
    source_status: Optional[PropertySourceStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List all property inventory sources."""
    service = PropertySourceService(db)
    return service.list_sources(
        source_type=source_type, source_status=source_status, skip=skip, limit=limit
    )


@router.post("", response_model=PropertySourceResponse, status_code=status.HTTP_201_CREATED)
def create_property_source(
    data: PropertySourceCreate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Register a new property source."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertySourceService(db)
    return service.create_source(data, actor_id=x_admin_id)


@router.get("/{source_id}", response_model=PropertySourceResponse)
def get_property_source(
    source_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve details for a specific property source."""
    service = PropertySourceService(db)
    return service.get_source_or_404(source_id)


@router.patch("/{source_id}", response_model=PropertySourceResponse)
def update_property_source(
    source_id: uuid.UUID,
    data: PropertySourceUpdate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Update configuration or details of a property source."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertySourceService(db)
    return service.update_source(source_id, data, actor_id=x_admin_id)


@router.post("/{source_id}/activate", response_model=PropertySourceResponse)
def activate_property_source(
    source_id: uuid.UUID,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Activate a property source."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertySourceService(db)
    return service.activate_source(source_id, actor_id=x_admin_id)


@router.post("/{source_id}/deactivate", response_model=PropertySourceResponse)
def deactivate_property_source(
    source_id: uuid.UUID,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Deactivate a property source."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertySourceService(db)
    return service.deactivate_source(source_id, actor_id=x_admin_id)
