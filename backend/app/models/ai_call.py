import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import AITaskType, AICallStatus


class AICall(Base):
    __tablename__ = "ai_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    request_id = Column(String(100), unique=True, nullable=False, index=True)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    conversation_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    task_type = Column(
        SAEnum(AITaskType, name="ai_task_type_enum", native_enum=True),
        nullable=False,
        index=True,
    )
    provider = Column(String(50), nullable=False)
    model = Column(String(100), nullable=False)
    prompt_name = Column(String(100), nullable=False)
    prompt_version = Column(String(50), nullable=False)
    status = Column(
        SAEnum(AICallStatus, name="ai_call_status_enum", native_enum=True),
        nullable=False,
        default=AICallStatus.STARTED,
        index=True,
    )
    input_token_count = Column(Integer, nullable=True)
    output_token_count = Column(Integer, nullable=True)
    total_token_count = Column(Integer, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    error_type = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
