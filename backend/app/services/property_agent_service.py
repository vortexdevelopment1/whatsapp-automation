import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.property_agent import PropertyAgent
from app.models.property_source import PropertySource
from app.models.enums import PropertyAgentStatus
from app.schemas.property_agent import PropertyAgentCreate, PropertyAgentUpdate
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.services.phone_service import normalize_phone_number, PhoneNormalizationError


class PropertyAgentService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    def get_agent_or_404(self, agent_id: uuid.UUID) -> PropertyAgent:
        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == agent_id).first()
        if not agent:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property agent with ID '{agent_id}' not found.",
            )
        return agent

    def create_agent(self, data: PropertyAgentCreate, actor_id: str = "system") -> PropertyAgent:
        phone_normalized = None
        if data.phone:
            try:
                phone_normalized = normalize_phone_number(data.phone)
            except PhoneNormalizationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid phone number: {str(e)}",
                )

        if data.source_id:
            source = self.db.query(PropertySource).filter(PropertySource.id == data.source_id).first()
            if not source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Source with ID '{data.source_id}' does not exist.",
                )

        agent = PropertyAgent(
            full_name=data.full_name,
            agency_name=data.agency_name,
            registration_number=data.registration_number,
            phone=data.phone,
            phone_normalized=phone_normalized,
            email=data.email,
            status=data.status,
            source_id=data.source_id,
            external_reference=data.external_reference,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_AGENT_CREATED",
                entity_type="property_agent",
                entity_id=str(agent.id),
                new_value={
                    "full_name": agent.full_name,
                    "agency_name": agent.agency_name,
                    "phone": agent.phone,
                    "status": agent.status.value,
                },
            )
        )

        return agent

    def list_agents(
        self,
        search: Optional[str] = None,
        agency_name: Optional[str] = None,
        agent_status: Optional[PropertyAgentStatus] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[PropertyAgent]:
        query = self.db.query(PropertyAgent)
        if search:
            pattern = f"%{search}%"
            query = query.filter(
                or_(
                    PropertyAgent.full_name.ilike(pattern),
                    PropertyAgent.phone.ilike(pattern),
                    PropertyAgent.email.ilike(pattern),
                    PropertyAgent.agency_name.ilike(pattern),
                    PropertyAgent.registration_number.ilike(pattern),
                )
            )
        if agency_name:
            query = query.filter(PropertyAgent.agency_name.ilike(f"%{agency_name}%"))
        if agent_status:
            query = query.filter(PropertyAgent.status == agent_status)

        return query.order_by(PropertyAgent.created_at.desc()).offset(skip).limit(limit).all()

    def update_agent(
        self, agent_id: uuid.UUID, data: PropertyAgentUpdate, actor_id: str = "system"
    ) -> PropertyAgent:
        agent = self.get_agent_or_404(agent_id)
        old_val = {
            "full_name": agent.full_name,
            "agency_name": agent.agency_name,
            "phone": agent.phone,
            "status": agent.status.value,
        }

        update_dict = data.model_dump(exclude_unset=True)
        if "phone" in update_dict:
            phone_val = update_dict["phone"]
            if phone_val:
                try:
                    update_dict["phone_normalized"] = normalize_phone_number(phone_val)
                except PhoneNormalizationError as e:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid phone number: {str(e)}",
                    )
            else:
                update_dict["phone_normalized"] = None

        if "source_id" in update_dict and update_dict["source_id"]:
            source = self.db.query(PropertySource).filter(PropertySource.id == update_dict["source_id"]).first()
            if not source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Source with ID '{update_dict['source_id']}' does not exist.",
                )

        for key, value in update_dict.items():
            setattr(agent, key, value)

        self.db.commit()
        self.db.refresh(agent)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_AGENT_UPDATED",
                entity_type="property_agent",
                entity_id=str(agent.id),
                old_value=old_val,
                new_value={
                    "full_name": agent.full_name,
                    "agency_name": agent.agency_name,
                    "phone": agent.phone,
                    "status": agent.status.value,
                },
            )
        )

        return agent

    def archive_agent(self, agent_id: uuid.UUID, actor_id: str = "system") -> PropertyAgent:
        agent = self.get_agent_or_404(agent_id)
        old_status = agent.status.value
        agent.status = PropertyAgentStatus.ARCHIVED
        self.db.commit()
        self.db.refresh(agent)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_AGENT_ARCHIVED",
                entity_type="property_agent",
                entity_id=str(agent.id),
                old_value={"status": old_status},
                new_value={"status": agent.status.value},
            )
        )
        return agent
