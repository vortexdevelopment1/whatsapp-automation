import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.models.whatsapp import WhatsAppProfile
from app.models.enums import WhatsAppConnectionStatus
from app.schemas.whatsapp import WhatsAppProfileUpdate


class WhatsAppRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, profile_id: uuid.UUID) -> Optional[WhatsAppProfile]:
        return (
            self.db.query(WhatsAppProfile)
            .filter(WhatsAppProfile.id == profile_id)
            .first()
        )

    def get_by_agent_id(self, agent_id: uuid.UUID) -> Optional[WhatsAppProfile]:
        return (
            self.db.query(WhatsAppProfile)
            .filter(WhatsAppProfile.agent_id == agent_id)
            .first()
        )

    def get_by_phone_number_id(self, phone_number_id: str) -> Optional[WhatsAppProfile]:
        return (
            self.db.query(WhatsAppProfile)
            .filter(WhatsAppProfile.phone_number_id == phone_number_id)
            .first()
        )

    def get_or_create_for_agent(self, agent_id: uuid.UUID) -> WhatsAppProfile:
        profile = self.get_by_agent_id(agent_id)
        if not profile:
            profile = WhatsAppProfile(
                agent_id=agent_id,
                connection_status=WhatsAppConnectionStatus.NOT_CONFIGURED,
                webhook_verified=False,
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def update(self, profile: WhatsAppProfile, data: WhatsAppProfileUpdate) -> WhatsAppProfile:
        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(profile, field, value)
        self.db.commit()
        self.db.refresh(profile)
        return profile

    def save(self, profile: WhatsAppProfile) -> WhatsAppProfile:
        self.db.commit()
        self.db.refresh(profile)
        return profile
