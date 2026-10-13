import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.template import TemplateCreate, TemplateUpdate, TemplateResponse
from app.services.template_service import TemplateService

agent_templates_router = APIRouter(prefix="/agents/{agent_id}/templates", tags=["templates"])
templates_router = APIRouter(prefix="/templates", tags=["templates"])


@agent_templates_router.get("", response_model=List[TemplateResponse])
def list_agent_templates(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = TemplateService(db)
    return service.list_templates_for_agent(agent_id)


@agent_templates_router.post("", response_model=TemplateResponse, status_code=status.HTTP_201_CREATED)
def create_agent_template(
    agent_id: uuid.UUID,
    data: TemplateCreate,
    db: Session = Depends(get_db),
):
    service = TemplateService(db)
    return service.create_template(agent_id, data)


@templates_router.patch("/{template_id}", response_model=TemplateResponse)
def update_template(
    template_id: uuid.UUID,
    data: TemplateUpdate,
    db: Session = Depends(get_db),
):
    service = TemplateService(db)
    return service.update_template(template_id, data)
