import uuid
from sqlalchemy import Column, String, Text, DateTime, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import LeadSourceType, LeadSourceStatus


class LeadSource(Base):
    __tablename__ = "lead_sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    source_type = Column(
        SAEnum(LeadSourceType, name="lead_source_type_enum", native_enum=True),
        nullable=False,
        default=LeadSourceType.MANUAL,
    )
    description = Column(Text, nullable=True)
    status = Column(
        SAEnum(LeadSourceStatus, name="lead_source_status_enum", native_enum=True),
        nullable=False,
        default=LeadSourceStatus.ACTIVE,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    leads = relationship("Lead", back_populates="source")
