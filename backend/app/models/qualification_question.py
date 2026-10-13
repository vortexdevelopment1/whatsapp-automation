import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import QuestionAction, QuestionType, QualificationQuestionStatus


class QualificationQuestion(Base):
    __tablename__ = "qualification_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    field_name = Column(String(100), nullable=True, index=True)
    question_type = Column(
        SAEnum(QuestionType, name="question_type_enum", native_enum=True),
        nullable=False,
        default=QuestionType.MISSING_FIELD,
        index=True,
    )
    action = Column(
        SAEnum(QuestionAction, name="question_action_enum", native_enum=True),
        nullable=False,
        default=QuestionAction.ASK_FIELD,
        index=True,
    )
    status = Column(
        SAEnum(QualificationQuestionStatus, name="qualification_question_status_enum", native_enum=True),
        nullable=False,
        default=QualificationQuestionStatus.GENERATED,
        index=True,
    )
    question_text = Column(Text, nullable=True)
    reason = Column(String(255), nullable=True)
    context_data = Column(JSONB, nullable=False, default=dict)
    source = Column(String(50), nullable=False, default="SYSTEM")
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt_version = Column(String(50), nullable=True)
    clarification_attempts = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    answered_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    lead = relationship("Lead")
    message = relationship("WhatsAppMessage")
