import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import BrandingStatus


class AgentBrandingProfile(Base):
    __tablename__ = "agent_branding_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True
    )
    business_description = Column(Text, nullable=True)
    office_address = Column(Text, nullable=True)
    website = Column(String(512), nullable=True)
    profile_photo_url = Column(String(1024), nullable=True)
    digital_name_card_url = Column(String(1024), nullable=True)
    lanyard_artwork_url = Column(String(1024), nullable=True)
    branding_status = Column(
        SAEnum(BrandingStatus, name="branding_status_enum", native_enum=True),
        nullable=False,
        default=BrandingStatus.NOT_STARTED
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship
    agent = relationship("Agent", back_populates="branding_profile")
