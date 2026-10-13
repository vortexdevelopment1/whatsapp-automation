import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.whatsapp import WhatsAppProfileUpdate, WhatsAppProfileResponse
from app.services.whatsapp_service import WhatsAppService

router = APIRouter(prefix="/agents/{agent_id}/whatsapp", tags=["whatsapp"])


@router.get("", response_model=WhatsAppProfileResponse)
def get_whatsapp_config(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = WhatsAppService(db)
    return service.get_profile(agent_id)


@router.put("", response_model=WhatsAppProfileResponse)
def update_whatsapp_config(
    agent_id: uuid.UUID,
    data: WhatsAppProfileUpdate,
    db: Session = Depends(get_db),
):
    service = WhatsAppService(db)
    return service.update_profile(agent_id, data)
