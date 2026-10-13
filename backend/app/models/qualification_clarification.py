import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import ClarificationStatus


class QualificationClarification(Base):
    __tablename__ = "qualification_clarifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name = Column(String(100), nullable=False, index=True)
    reason = Column(String(255), nullable=False)
    proposed_value = Column(JSONB, nullable=True)
    status = Column(
        SAEnum(ClarificationStatus, name="clarification_status_enum", native_enum=True),
        nullable=False,
        default=ClarificationStatus.OPEN,
        index=True,
    )
    attempt_count = Column(Integer, nullable=False, default=1)
    last_question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qualification_questions.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolved_value = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    lead = relationship("Lead", backref="clarifications")
    last_question = relationship("QualificationQuestion")
