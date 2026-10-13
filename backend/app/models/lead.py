import uuid
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base
from app.models.enums import LeadStatus, ConsentStatus, OptOutStatus, ContactEligibility


class Lead(Base):
    __tablename__ = "leads"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=False)
    phone_normalized = Column(String(50), nullable=False, index=True)
    email = Column(String(255), nullable=True, index=True)
    source_id = Column(
        UUID(as_uuid=True),
        ForeignKey("lead_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        SAEnum(LeadStatus, name="lead_status_enum", native_enum=True),
        nullable=False,
        default=LeadStatus.NEW,
        index=True,
    )
    consent_status = Column(
        SAEnum(ConsentStatus, name="consent_status_enum", native_enum=True),
        nullable=False,
        default=ConsentStatus.UNKNOWN,
    )
    opt_out_status = Column(
        SAEnum(OptOutStatus, name="opt_out_status_enum", native_enum=True),
        nullable=False,
        default=OptOutStatus.ACTIVE,
    )
    contact_eligibility = Column(
        SAEnum(ContactEligibility, name="contact_eligibility_enum", native_enum=True),
        nullable=False,
        default=ContactEligibility.UNKNOWN,
    )
    assigned_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assigned_whatsapp_profile_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    duplicate_override = Column(Boolean, nullable=False, default=False)
    duplicate_override_reason = Column(Text, nullable=True)
    duplicate_of_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    # Relationships
    source = relationship("LeadSource", back_populates="leads")
    assigned_agent = relationship("Agent")
    assigned_whatsapp_profile = relationship("WhatsAppProfile")
    routing_decisions = relationship(
        "LeadRoutingDecision",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="desc(LeadRoutingDecision.created_at)",
    )
    outreach_records = relationship(
        "LeadOutreach",
        back_populates="lead",
        cascade="all, delete-orphan",
        order_by="desc(LeadOutreach.created_at)",
    )
    tenant_requirement = relationship(
        "TenantRequirement",
        uselist=False,
        back_populates="lead",
        cascade="all, delete-orphan",
    )

