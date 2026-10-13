import uuid
from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import AgentStatus, AuthorizationStatus


class Agent(Base):
    __tablename__ = "agents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    agency_name = Column(String(255), nullable=False)
    designation = Column(String(255), nullable=True)
    registration_number = Column(String(100), nullable=True, index=True)
    phone = Column(String(50), nullable=True, index=True)
    email = Column(String(255), nullable=True, index=True)
    profile_photo_url = Column(String(1024), nullable=True)
    status = Column(
        SAEnum(AgentStatus, name="agent_status_enum", native_enum=True),
        nullable=False,
        default=AgentStatus.DRAFT,
        index=True
    )
    authorization_status = Column(
        SAEnum(AuthorizationStatus, name="authorization_status_enum", native_enum=True),
        nullable=False,
        default=AuthorizationStatus.PENDING,
        index=True
    )
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    branding_profile = relationship("AgentBrandingProfile", back_populates="agent", uselist=False, cascade="all, delete-orphan")
    whatsapp_profile = relationship("WhatsAppProfile", back_populates="agent", uselist=False, cascade="all, delete-orphan")
    templates = relationship("MessageTemplate", back_populates="agent", cascade="all, delete-orphan")
