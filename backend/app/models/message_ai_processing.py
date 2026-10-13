import uuid
from sqlalchemy import Column, String, Numeric, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import MessageAIProcessingStatus


class MessageAIProcessing(Base):
    __tablename__ = "message_ai_processing"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ai_call_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_calls.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intent = Column(String(50), nullable=True, index=True)
    intent_confidence = Column(Numeric(5, 4), nullable=True)
    status = Column(
        SAEnum(MessageAIProcessingStatus, name="message_ai_processing_status_enum", native_enum=True),
        nullable=False,
        default=MessageAIProcessingStatus.PROCESSED,
        index=True,
    )
    accepted_fields = Column(JSONB, nullable=False, default=list)
    proposed_fields = Column(JSONB, nullable=False, default=list)
    rejected_fields = Column(JSONB, nullable=False, default=list)
    clarification_fields = Column(JSONB, nullable=False, default=list)
    raw_extraction = Column(JSONB, nullable=True)
    message_summary = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    response_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    message = relationship("WhatsAppMessage", foreign_keys=[message_id])
    response_message = relationship("WhatsAppMessage", foreign_keys=[response_message_id])
    lead = relationship("Lead")
    ai_call = relationship("AICall")
