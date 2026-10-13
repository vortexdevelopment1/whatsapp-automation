import uuid
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import TemplateStatus


class MessageTemplate(Base):
    __tablename__ = "message_templates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True
    )
    template_name = Column(String(255), nullable=False)
    meta_template_name = Column(String(255), nullable=True)
    language = Column(String(20), nullable=False, default="en_US")
    category = Column(String(50), nullable=True)
    body = Column(Text, nullable=False)
    status = Column(
        SAEnum(TemplateStatus, name="template_status_enum", native_enum=True),
        nullable=False,
        default=TemplateStatus.DRAFT
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationship
    agent = relationship("Agent", back_populates="templates")
