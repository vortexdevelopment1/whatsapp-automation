import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import OutreachType, OutreachStatus


class LeadOutreach(Base):
    __tablename__ = "lead_outreach"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    whatsapp_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    outreach_type = Column(
        SAEnum(OutreachType, name="outreach_type_enum", native_enum=True),
        nullable=False,
        default=OutreachType.INITIAL,
    )
    status = Column(
        SAEnum(OutreachStatus, name="outreach_status_enum", native_enum=True),
        nullable=False,
        default=OutreachStatus.QUEUED,
        index=True,
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    lead = relationship("Lead", back_populates="outreach_records")
    whatsapp_message = relationship("WhatsAppMessage")
    template = relationship("MessageTemplate")
