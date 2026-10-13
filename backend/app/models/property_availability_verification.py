import uuid
from sqlalchemy import (
    Column,
    String,
    Numeric,
    Integer,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PropertyAvailabilityVerification(Base):
    """
    Module 4 Phase 6: Property Availability Verification.
    Tracks structured verification results from external property agent replies
    or operator manual overrides with full audit provenance.
    """

    __tablename__ = "property_availability_verifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_match_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_matches.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    property_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agents.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    outreach_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agent_outreach.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    intent = Column(String(50), nullable=True)
    availability_status = Column(String(50), nullable=False, default="UNKNOWN", index=True)

    asking_price = Column(Numeric(12, 2), nullable=True)
    currency = Column(String(10), nullable=False, default="SGD")
    available_from = Column(Date, nullable=True)
    minimum_lease_months = Column(Integer, nullable=True)
    maximum_lease_months = Column(Integer, nullable=True)
    furnishing = Column(String(50), nullable=True)

    viewing_possible = Column(Boolean, nullable=True)
    viewing_notes = Column(String(500), nullable=True)

    conditions = Column(JSONB, nullable=True)
    special_restrictions = Column(JSONB, nullable=True)
    extracted_fields = Column(JSONB, nullable=True)

    verification_status = Column(String(50), nullable=False, default="CONFIRMED", index=True)
    verification_source = Column(String(50), nullable=False, default="AGENT_REPLY", index=True)

    confidence_summary = Column(JSONB, nullable=True)
    overall_confidence = Column(Numeric(4, 3), nullable=True)

    ai_call_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ai_calls.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes = Column(Text, nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    property_match = relationship("PropertyMatch", back_populates="verification_records")
    listing = relationship("PropertyListing")
    property_agent = relationship("PropertyAgent")
    outreach = relationship("PropertyAgentOutreach")
    source_message = relationship("WhatsAppMessage")
