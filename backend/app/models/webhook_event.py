import uuid
from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import WebhookProcessingStatus


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider = Column(String(50), nullable=False, default="meta")
    provider_event_id = Column(String(255), nullable=True, index=True)
    event_type = Column(String(100), nullable=False)
    payload = Column(JSONB, nullable=False)
    processing_status = Column(
        SAEnum(WebhookProcessingStatus, name="webhook_processing_status_enum", native_enum=True),
        nullable=False,
        default=WebhookProcessingStatus.RECEIVED,
        index=True
    )
    error_message = Column(Text, nullable=True)
    received_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
