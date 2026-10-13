import uuid
from sqlalchemy.orm import Session
from app.models.branding import AgentBrandingProfile
from app.repositories.branding_repo import BrandingRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.branding import BrandingUpdate
from app.schemas.audit import AuditLogCreate
from app.services.agent_service import AgentService


class BrandingService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = BrandingRepository(db)
        self.agent_service = AgentService(db)
        self.audit_repo = AuditRepository(db)

    def get_branding(self, agent_id: uuid.UUID) -> AgentBrandingProfile:
        self.agent_service.get_agent_or_404(agent_id)
        return self.repo.get_or_create_for_agent(agent_id)

    def update_branding(
        self, agent_id: uuid.UUID, data: BrandingUpdate, actor_id: str = "system"
    ) -> AgentBrandingProfile:
        self.agent_service.get_agent_or_404(agent_id)
        profile = self.repo.get_or_create_for_agent(agent_id)
        old_data = {
            "business_description": profile.business_description,
            "office_address": profile.office_address,
            "website": profile.website,
            "branding_status": profile.branding_status.value if profile.branding_status else None,
        }
        updated = self.repo.update(profile, data)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="BRANDING_UPDATED",
                entity_type="AgentBrandingProfile",
                entity_id=str(updated.id),
                old_value=old_data,
                new_value=data.model_dump(exclude_unset=True),
            )
        )
        return updated
