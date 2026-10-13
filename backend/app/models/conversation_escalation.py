import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import EscalationStatus, EscalationReason


class ConversationEscalation(Base):
    __tablename__ = "conversation_escalations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(UUID(as_uuid=True), nullable=True)
    reason_code = Column(
        SAEnum(EscalationReason, name="escalation_reason_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    description = Column(Text, nullable=True)
    status = Column(
        SAEnum(EscalationStatus, name="escalation_status_enum", native_enum=True),
        nullable=False,
        default=EscalationStatus.OPEN,
        index=True,
    )
    assigned_to = Column(String(100), nullable=True)
    created_by = Column(String(100), nullable=False, default="system")
    resolution_notes = Column(Text, nullable=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    lead = relationship("Lead", backref="escalations")
