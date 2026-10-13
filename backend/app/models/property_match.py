import uuid
from sqlalchemy import Column, String, Numeric, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PropertyMatch(Base):
    __tablename__ = "property_matches"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    matching_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_matching_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    match_status = Column(String(50), nullable=False, default="CANDIDATE", index=True)
    hard_filter_passed = Column(Boolean, nullable=True, default=False)
    hard_filter_result = Column(JSONB, nullable=True)
    filter_rule_version = Column(String(50), nullable=True)
    matching_config_version = Column(String(50), nullable=True)

    match_score = Column(Numeric(5, 2), nullable=True)
    score_breakdown = Column(JSONB, nullable=True)
    rank = Column(Integer, nullable=True, index=True)
    scoring_config_version = Column(String(50), nullable=True)
    scoring_explanation = Column(String(1000), nullable=True)
    is_stale = Column(Boolean, nullable=False, default=False)
    stale_reason = Column(String(255), nullable=True)
    agent_verification_status = Column(String(50), nullable=True, default="NOT_CHECKED")
    availability_status = Column(String(50), nullable=True)

    # Manual Override Tracking
    manual_override = Column(Boolean, nullable=False, default=False)
    manual_override_by = Column(String(100), nullable=True)
    manual_override_at = Column(DateTime(timezone=True), nullable=True)
    manual_override_reason = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    lead = relationship("Lead")
    property = relationship("Property", back_populates="matches")
    listing = relationship("PropertyListing", back_populates="matches")
    matching_run = relationship("PropertyMatchingRun", back_populates="matches")
    outreach_records = relationship(
        "PropertyAgentOutreach",
        back_populates="property_match",
        cascade="all, delete-orphan",
        order_by="desc(PropertyAgentOutreach.created_at)",
    )
    verification_records = relationship(
        "PropertyAvailabilityVerification",
        back_populates="property_match",
        cascade="all, delete-orphan",
        order_by="desc(PropertyAvailabilityVerification.created_at)",
    )
    followup_records = relationship(
        "PropertyAgentFollowUp",
        back_populates="property_match",
        cascade="all, delete-orphan",
        order_by="desc(PropertyAgentFollowUp.created_at)",
    )



