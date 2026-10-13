import uuid
from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import RequirementFieldStatus, RequirementSourceType


class TenantRequirementHistory(Base):
    __tablename__ = "tenant_requirement_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant_requirements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_name = Column(String(100), nullable=False, index=True)
    value = Column(JSONB, nullable=True)
    confidence = Column(Numeric(5, 4), nullable=True)
    source_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        SAEnum(RequirementFieldStatus, name="requirement_field_status_enum", native_enum=True),
        nullable=False,
        default=RequirementFieldStatus.CONFIRMED,
        index=True,
    )
    source_type = Column(
        SAEnum(RequirementSourceType, name="requirement_source_type_enum", native_enum=True),
        nullable=False,
        default=RequirementSourceType.HUMAN_OPERATOR,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    tenant_requirement = relationship("TenantRequirement", back_populates="field_history")
    source_message = relationship("WhatsAppMessage")
