import uuid
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class LeadRoutingDecision(Base):
    __tablename__ = "lead_routing_decisions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    route_name = Column(String(100), nullable=False)
    reason = Column(JSONB, nullable=False)
    rule_version = Column(String(50), nullable=True)
    manual_override = Column(Boolean, nullable=False, default=False)
    overridden_by = Column(UUID(as_uuid=True), nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationship
    lead = relationship("Lead", back_populates="routing_decisions")
