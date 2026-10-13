import uuid
from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import QualificationStatus


class QualificationDecision(Base):
    __tablename__ = "qualification_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tenant_requirement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenant_requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision = Column(
        SAEnum(QualificationStatus, name="qualification_status_enum", native_enum=True, create_type=False),
        nullable=False,
        index=True,
    )
    reason_codes = Column(JSONB, nullable=False, default=list)
    rule_version = Column(String(50), nullable=False, default="v1")
    completion_percentage = Column(Integer, nullable=False, default=0)
    missing_fields = Column(JSONB, nullable=False, default=list)
    blocking_fields = Column(JSONB, nullable=False, default=list)
    evaluated_by = Column(String(100), nullable=False, default="system")
    evaluation_source = Column(String(50), nullable=False, default="SYSTEM")
    override_reason = Column(Text, nullable=True)
    applied = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    lead = relationship("Lead")
    tenant_requirement = relationship("TenantRequirement")
