import uuid
from sqlalchemy import Column, String, Integer, Numeric, Date, DateTime, Boolean, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import QualificationStatus


class TenantRequirement(Base):
    __tablename__ = "tenant_requirements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )
    preferred_locations = Column(JSONB, nullable=True)
    budget_min = Column(Numeric(12, 2), nullable=True)
    budget_max = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), nullable=False, default="SGD")
    property_type = Column(String(100), nullable=True)
    bedrooms = Column(Integer, nullable=True)
    move_in_date = Column(Date, nullable=True)
    lease_duration_months = Column(Integer, nullable=True)
    occupants = Column(Integer, nullable=True)
    furnishing = Column(String(50), nullable=True)
    special_requirements = Column(JSONB, nullable=True)
    qualification_status = Column(
        SAEnum(QualificationStatus, name="qualification_status_enum", native_enum=True),
        nullable=False,
        default=QualificationStatus.NOT_STARTED,
        index=True,
    )
    completion_percentage = Column(Integer, nullable=False, default=0)
    ai_paused = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    lead = relationship("Lead", back_populates="tenant_requirement")
    field_history = relationship(
        "TenantRequirementHistory",
        back_populates="tenant_requirement",
        cascade="all, delete-orphan",
        order_by="desc(TenantRequirementHistory.created_at)",
    )
