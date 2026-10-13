import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.models.branding import AgentBrandingProfile
from app.models.enums import BrandingStatus
from app.schemas.branding import BrandingUpdate


class BrandingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_agent_id(self, agent_id: uuid.UUID) -> Optional[AgentBrandingProfile]:
        return (
            self.db.query(AgentBrandingProfile)
            .filter(AgentBrandingProfile.agent_id == agent_id)
            .first()
        )

    def get_or_create_for_agent(self, agent_id: uuid.UUID) -> AgentBrandingProfile:
        profile = self.get_by_agent_id(agent_id)
        if not profile:
            profile = AgentBrandingProfile(
                agent_id=agent_id,
                branding_status=BrandingStatus.NOT_STARTED,
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update(self, profile: AgentBrandingProfile, data: BrandingUpdate) -> AgentBrandingProfile:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile
