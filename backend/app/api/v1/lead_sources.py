import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.enums import LeadSourceStatus
from app.schemas.lead_source import LeadSourceCreate, LeadSourceUpdate, LeadSourceResponse
from app.services.lead_source_service import LeadSourceService

router = APIRouter(prefix="/lead-sources", tags=["lead-sources"])


@router.get("", response_model=List[LeadSourceResponse])
def list_lead_sources(
    status: Optional[LeadSourceStatus] = Query(None, description="Filter by status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = LeadSourceService(db)
    return service.list_sources(status=status, skip=skip, limit=limit)


@router.post("", response_model=LeadSourceResponse, status_code=status.HTTP_201_CREATED)
def create_lead_source(
    data: LeadSourceCreate,
    db: Session = Depends(get_db),
):
    service = LeadSourceService(db)
    return service.create_source(data)


@router.patch("/{source_id}", response_model=LeadSourceResponse)
def update_lead_source(
    source_id: uuid.UUID,
    data: LeadSourceUpdate,
    db: Session = Depends(get_db),
):
    service = LeadSourceService(db)
    return service.update_source(source_id, data)
