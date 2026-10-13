import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.branding import BrandingUpdate, BrandingResponse
from app.services.branding_service import BrandingService

router = APIRouter(prefix="/agents/{agent_id}/branding", tags=["branding"])


@router.get("", response_model=BrandingResponse)
def get_agent_branding(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = BrandingService(db)
    return service.get_branding(agent_id)


@router.put("", response_model=BrandingResponse)
def update_agent_branding(
    agent_id: uuid.UUID,
    data: BrandingUpdate,
    db: Session = Depends(get_db),
):
    service = BrandingService(db)
    return service.update_branding(agent_id, data)
