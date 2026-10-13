import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import MessageDirection, MessageType


class WhatsAppMessage(Base):
    __tablename__ = "whatsapp_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    whatsapp_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True
    )
    provider_message_id = Column(String(255), unique=True, nullable=True, index=True)
    direction = Column(
        SAEnum(MessageDirection, name="message_direction_enum", native_enum=True),
        nullable=False
    )
    message_type = Column(
        SAEnum(MessageType, name="message_type_enum", native_enum=True),
        nullable=False,
        default=MessageType.TEXT
    )
    sender = Column(String(50), nullable=True)
    recipient = Column(String(50), nullable=True)
    content = Column(Text, nullable=True)
    provider_status = Column(String(50), nullable=True)
    raw_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationship
    whatsapp_profile = relationship("WhatsAppProfile", back_populates="messages")
