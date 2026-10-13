import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.agent import Agent
from app.models.enums import AgentStatus, AuthorizationStatus
from app.schemas.agent import AgentCreate, AgentUpdate


class AgentRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, agent_id: uuid.UUID) -> Optional[Agent]:
        return self.db.query(Agent).filter(Agent.id == agent_id).first()

    def list_agents(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[AgentStatus] = None,
        authorization_status: Optional[AuthorizationStatus] = None,
        search: Optional[str] = None,
    ) -> List[Agent]:
        query = self.db.query(Agent)

        if status:
            query = query.filter(Agent.status == status)
        if authorization_status:
            query = query.filter(Agent.authorization_status == authorization_status)
        if search:
            search_filter = f"%{search}%"
            query = query.filter(
                (Agent.full_name.ilike(search_filter))
                | (Agent.display_name.ilike(search_filter))
                | (Agent.agency_name.ilike(search_filter))
                | (Agent.email.ilike(search_filter))
                | (Agent.phone.ilike(search_filter))
                | (Agent.registration_number.ilike(search_filter))
            )

        return query.order_by(Agent.created_at.desc()).offset(skip).limit(limit).all()

    def create(self, data: AgentCreate) -> Agent:
        agent = Agent(
            full_name=data.full_name,
            display_name=data.display_name,
            agency_name=data.agency_name,
            designation=data.designation,
            registration_number=data.registration_number,
            phone=data.phone,
            email=data.email,
            profile_photo_url=data.profile_photo_url,
            notes=data.notes,
            status=AgentStatus.DRAFT,
            authorization_status=AuthorizationStatus.PENDING,
        )
        self.db.add(agent)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def update(self, agent: Agent, data: AgentUpdate) -> Agent:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(agent, field, value)
        self.db.commit()
        self.db.refresh(agent)
        return agent

    def save(self, agent: Agent) -> Agent:
        self.db.commit()
        self.db.refresh(agent)
        return agent
