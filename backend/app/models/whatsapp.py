import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import WhatsAppConnectionStatus


class WhatsAppProfile(Base):
    __tablename__ = "whatsapp_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True
    )
    meta_business_account_id = Column(String(128), nullable=True)
    phone_number_id = Column(String(128), nullable=True, index=True)
    display_phone_number = Column(String(50), nullable=True)
    business_display_name = Column(String(255), nullable=True)
    connection_status = Column(
        SAEnum(WhatsAppConnectionStatus, name="whatsapp_connection_status_enum", native_enum=True),
        nullable=False,
        default=WhatsAppConnectionStatus.NOT_CONFIGURED
    )
    webhook_verified = Column(Boolean, nullable=False, default=False)
    last_webhook_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    agent = relationship("Agent", back_populates="whatsapp_profile")
    messages = relationship("WhatsAppMessage", back_populates="whatsapp_profile", cascade="all, delete-orphan")
