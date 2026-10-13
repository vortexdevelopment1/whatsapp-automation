import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import SummaryGeneratedBy


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    summary_text = Column(Text, nullable=False)
    structured_summary = Column(JSONB, nullable=True)
    summary_version = Column(Integer, nullable=False, default=1)
    last_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    generated_by = Column(
        SAEnum(SummaryGeneratedBy, name="summary_generated_by_enum", native_enum=True),
        nullable=False,
        default=SummaryGeneratedBy.SYSTEM,
    )
    ai_call_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_calls.id", ondelete="SET NULL"),
        nullable=True,
    )
    prompt_version = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
