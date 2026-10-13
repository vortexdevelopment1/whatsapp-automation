import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.enums import AgentStatus, AuthorizationStatus
from app.schemas.agent import AgentCreate, AgentUpdate, AgentResponse
from app.services.agent_service import AgentService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", response_model=AgentResponse, status_code=status.HTTP_201_CREATED)
def create_agent(
    data: AgentCreate,
    db: Session = Depends(get_db),
):
    service = AgentService(db)
    return service.create_agent(data)


@router.get("", response_model=List[AgentResponse])
def list_agents(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status: Optional[AgentStatus] = None,
    authorization_status: Optional[AuthorizationStatus] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    service = AgentService(db)
    return service.list_agents(
        skip=skip,
        limit=limit,
        status=status,
        authorization_status=authorization_status,
        search=search,
    )


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = AgentService(db)
    return service.get_agent_or_404(agent_id)


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(
    agent_id: uuid.UUID,
    data: AgentUpdate,
    db: Session = Depends(get_db),
):
    service = AgentService(db)
    return service.update_agent(agent_id, data)


@router.post("/{agent_id}/activate", response_model=AgentResponse)
def activate_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = AgentService(db)
    return service.activate_agent(agent_id)


@router.post("/{agent_id}/deactivate", response_model=AgentResponse)
def deactivate_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = AgentService(db)
    return service.deactivate_agent(agent_id)


@router.post("/{agent_id}/archive", response_model=AgentResponse)
def archive_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = AgentService(db)
    return service.archive_agent(agent_id)
