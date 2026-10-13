import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import PropertyAgentStatus
from app.schemas.property_agent import (
    PropertyAgentCreate,
    PropertyAgentUpdate,
    PropertyAgentResponse,
)
from app.services.property_agent_service import PropertyAgentService

router = APIRouter(prefix="/property-agents", tags=["property-agents"])


@router.get("", response_model=List[PropertyAgentResponse])
def list_property_agents(
    search: Optional[str] = Query(None, description="Search by name, phone, email, agency, or reg no"),
    agency_name: Optional[str] = Query(None, description="Filter by agency name"),
    agent_status: Optional[PropertyAgentStatus] = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List external property/listing agents."""
    service = PropertyAgentService(db)
    return service.list_agents(
        search=search,
        agency_name=agency_name,
        agent_status=agent_status,
        skip=skip,
        limit=limit,
    )


@router.post("", response_model=PropertyAgentResponse, status_code=status.HTTP_201_CREATED)
def create_property_agent(
    data: PropertyAgentCreate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Create a new external property agent record."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyAgentService(db)
    return service.create_agent(data, actor_id=x_admin_id)


@router.get("/{agent_id}", response_model=PropertyAgentResponse)
def get_property_agent(
    agent_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Get details of a specific external property agent."""
    service = PropertyAgentService(db)
    return service.get_agent_or_404(agent_id)


@router.patch("/{agent_id}", response_model=PropertyAgentResponse)
def update_property_agent(
    agent_id: uuid.UUID,
    data: PropertyAgentUpdate,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Update details of a property agent."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyAgentService(db)
    return service.update_agent(agent_id, data, actor_id=x_admin_id)


@router.post("/{agent_id}/archive", response_model=PropertyAgentResponse)
def archive_property_agent(
    agent_id: uuid.UUID,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Archive an external property agent."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    service = PropertyAgentService(db)
    return service.archive_agent(agent_id, actor_id=x_admin_id)
