import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.tenant_requirement import (
    TenantRequirementCreate,
    TenantRequirementUpdate,
    TenantRequirementResponse,
    TenantRequirementHistoryResponse,
    QualificationProgressResponse,
)
from app.services.tenant_requirement_service import TenantRequirementService

router = APIRouter(prefix="/leads/{lead_id}", tags=["tenant-requirements"])


@router.get("/requirements", response_model=TenantRequirementResponse)
def get_tenant_requirements(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = TenantRequirementService(db)
    return service.get_requirement_or_404(lead_id)


@router.post("/requirements", response_model=TenantRequirementResponse, status_code=status.HTTP_201_CREATED)
def create_tenant_requirements(
    lead_id: uuid.UUID,
    data: TenantRequirementCreate,
    db: Session = Depends(get_db),
):
    service = TenantRequirementService(db)
    return service.create_requirement(lead_id, data)


@router.patch("/requirements", response_model=TenantRequirementResponse)
def update_tenant_requirements(
    lead_id: uuid.UUID,
    data: TenantRequirementUpdate,
    db: Session = Depends(get_db),
):
    service = TenantRequirementService(db)
    return service.update_requirement(lead_id, data)


@router.get("/requirements/history", response_model=List[TenantRequirementHistoryResponse])
def get_tenant_requirements_history(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = TenantRequirementService(db)
    return service.list_history(lead_id)


@router.get("/requirements/missing", response_model=List[str])
def get_missing_requirements(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = TenantRequirementService(db)
    req = service.get_requirement_or_404(lead_id)
    return service.get_missing_required_fields(req)


@router.get("/qualification-progress", response_model=QualificationProgressResponse)
def get_qualification_progress(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = TenantRequirementService(db)
    return service.get_qualification_progress(lead_id)
