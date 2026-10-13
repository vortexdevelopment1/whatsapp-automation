import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.agent import Agent
from app.models.enums import AgentStatus, AuthorizationStatus
from app.repositories.agent_repo import AgentRepository
from app.repositories.branding_repo import BrandingRepository
from app.repositories.whatsapp_repo import WhatsAppRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.agent import AgentCreate, AgentUpdate
from app.schemas.audit import AuditLogCreate


class AgentService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AgentRepository(db)
        self.branding_repo = BrandingRepository(db)
        self.whatsapp_repo = WhatsAppRepository(db)
        self.audit_repo = AuditRepository(db)

    def get_agent_or_404(self, agent_id: uuid.UUID) -> Agent:
        agent = self.repo.get_by_id(agent_id)
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Agent with id {agent_id} not found"
            )
        return agent

    def list_agents(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[AgentStatus] = None,
        authorization_status: Optional[AuthorizationStatus] = None,
        search: Optional[str] = None,
    ) -> List[Agent]:
        return self.repo.list_agents(
            skip=skip,
            limit=limit,
            status=status,
            authorization_status=authorization_status,
            search=search,
        )

    def create_agent(self, data: AgentCreate, actor_id: str = "system") -> Agent:
        agent = self.repo.create(data)
        # Ensure default branding and whatsapp profile entities exist
        self.branding_repo.get_or_create_for_agent(agent.id)
        self.whatsapp_repo.get_or_create_for_agent(agent.id)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="AGENT_CREATED",
                entity_type="Agent",
                entity_id=str(agent.id),
                new_value={"full_name": agent.full_name, "agency_name": agent.agency_name},
            )
        )
        return agent

    def update_agent(self, agent_id: uuid.UUID, data: AgentUpdate, actor_id: str = "system") -> Agent:
        agent = self.get_agent_or_404(agent_id)

        old_values = {
            "full_name": agent.full_name,
            "authorization_status": agent.authorization_status.value,
            "status": agent.status.value,
        }

        # If updating authorization_status to non-VERIFIED while agent is ACTIVE, force INACTIVE
        if data.authorization_status and data.authorization_status != AuthorizationStatus.VERIFIED:
            if agent.status == AgentStatus.ACTIVE:
                agent.status = AgentStatus.INACTIVE

        agent = self.repo.update(agent, data)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="AGENT_UPDATED",
                entity_type="Agent",
                entity_id=str(agent.id),
                old_value=old_values,
                new_value=data.model_dump(exclude_unset=True),
            )
        )
        return agent

    def activate_agent(self, agent_id: uuid.UUID, actor_id: str = "system") -> Agent:
        agent = self.get_agent_or_404(agent_id)

        # STRICT RULE: ACTIVE is allowed only if authorization_status = VERIFIED
        if agent.authorization_status != AuthorizationStatus.VERIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot activate agent: authorization status must be VERIFIED before activation."
            )

        old_status = agent.status.value
        agent.status = AgentStatus.ACTIVE
        agent = self.repo.save(agent)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="AGENT_ACTIVATED",
                entity_type="Agent",
                entity_id=str(agent.id),
                old_value={"status": old_status},
                new_value={"status": agent.status.value},
            )
        )
        return agent

    def deactivate_agent(self, agent_id: uuid.UUID, actor_id: str = "system") -> Agent:
        agent = self.get_agent_or_404(agent_id)
        old_status = agent.status.value
        agent.status = AgentStatus.INACTIVE
        agent = self.repo.save(agent)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="AGENT_DEACTIVATED",
                entity_type="Agent",
                entity_id=str(agent.id),
                old_value={"status": old_status},
                new_value={"status": agent.status.value},
            )
        )
        return agent

    def archive_agent(self, agent_id: uuid.UUID, actor_id: str = "system") -> Agent:
        agent = self.get_agent_or_404(agent_id)
        old_status = agent.status.value
        agent.status = AgentStatus.ARCHIVED
        agent = self.repo.save(agent)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="AGENT_ARCHIVED",
                entity_type="Agent",
                entity_id=str(agent.id),
                old_value={"status": old_status},
                new_value={"status": agent.status.value},
            )
        )
        return agent
