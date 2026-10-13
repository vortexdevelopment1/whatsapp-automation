import uuid
from sqlalchemy import Column, String, Integer, Numeric, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import MatchingRunStatus


class PropertyMatchingRun(Base):
    __tablename__ = "property_matching_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    qualification_decision_id = Column(
        UUID(as_uuid=True),
        ForeignKey("qualification_decisions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    config_version = Column(String(50), nullable=False, default="v1.0")
    status = Column(
        SAEnum(MatchingRunStatus, name="matching_run_status_enum"),
        nullable=False,
        default=MatchingRunStatus.PENDING,
        index=True,
    )

    total_inventory_considered = Column(Integer, nullable=False, default=0)
    eligible_candidates = Column(Integer, nullable=False, default=0)
    filtered_candidates = Column(Integer, nullable=False, default=0)
    needs_review_candidates = Column(Integer, nullable=False, default=0)

    # Phase 4 Scoring Metrics
    scored_candidates = Column(Integer, nullable=False, default=0)
    ready_for_verification_candidates = Column(Integer, nullable=False, default=0)
    below_threshold_candidates = Column(Integer, nullable=False, default=0)
    scoring_config_version = Column(String(50), nullable=True)
    top_score = Column(Numeric(5, 2), nullable=True)

    requirement_snapshot = Column(JSONB, nullable=True)
    error_message = Column(String(1000), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    lead = relationship("Lead")
    qualification_decision = relationship("QualificationDecision")
    matches = relationship(
        "PropertyMatch",
        back_populates="matching_run",
        cascade="all, delete-orphan",
    )
