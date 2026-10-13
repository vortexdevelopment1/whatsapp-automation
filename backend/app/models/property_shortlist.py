import uuid
from sqlalchemy import Column, String, Numeric, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PropertyShortlist(Base):
    __tablename__ = "property_shortlists"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    matching_run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_matching_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    version = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False, default="DRAFT", index=True)
    config_version = Column(String(50), nullable=False, default="1.0.0")
    created_by = Column(String(100), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    lead = relationship("Lead")
    matching_run = relationship("PropertyMatchingRun")
    items = relationship(
        "PropertyShortlistItem",
        back_populates="shortlist",
        cascade="all, delete-orphan",
        order_by="PropertyShortlistItem.position",
    )


class PropertyShortlistItem(Base):
    __tablename__ = "property_shortlist_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shortlist_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_shortlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_match_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    position = Column(Integer, nullable=False, default=1, index=True)
    shortlist_status = Column(String(50), nullable=False, default="VERIFIED_CANDIDATE", index=True)
    score_at_selection = Column(Numeric(5, 2), nullable=True)
    verification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_availability_verifications.id", ondelete="SET NULL"),
        nullable=True,
    )
    reason_codes = Column(JSONB, nullable=True)
    warnings = Column(JSONB, nullable=True)
    explanation = Column(String(1000), nullable=True)
    manual_override = Column(Boolean, nullable=False, default=False)
    manual_override_reason = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    shortlist = relationship("PropertyShortlist", back_populates="items")
    property_match = relationship("PropertyMatch")
    verification = relationship("PropertyAvailabilityVerification")
