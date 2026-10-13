import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import (
    ViewingAvailabilityRequestStatus,
    AgentAvailabilityResponseIntent,
    ViewingCorrelationStatus,
)


class ViewingAvailabilityRequest(Base):
    __tablename__ = "viewing_availability_requests"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_viewing_availability_request_idempotency"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    viewing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("viewings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_match_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    listing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_listings.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    property_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agent_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        SAEnum(ViewingAvailabilityRequestStatus, name="viewing_availability_request_status_enum", native_enum=True),
        nullable=False,
        default=ViewingAvailabilityRequestStatus.PENDING,
        index=True,
    )

    provider_message_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(255), nullable=False)

    outbound_message_text = Column(Text, nullable=True)
    raw_response_text = Column(Text, nullable=True)
    response_intent = Column(
        SAEnum(AgentAvailabilityResponseIntent, name="agent_availability_response_intent_enum", native_enum=True),
        nullable=True,
        index=True,
    )
    correlation_status = Column(
        SAEnum(ViewingCorrelationStatus, name="viewing_correlation_status_enum", native_enum=True),
        nullable=False,
        default=ViewingCorrelationStatus.RESOLVED,
        index=True,
    )
    agent_notes = Column(Text, nullable=True)
    request_metadata = Column("metadata", JSONB, nullable=True)

    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    viewing = relationship("Viewing")
    lead = relationship("Lead")
    property_match = relationship("PropertyMatch")
    listing = relationship("PropertyListing")
    property_agent = relationship("PropertyAgent")
    conversation = relationship("PropertyAgentConversation")

    def __repr__(self) -> str:
        return f"<ViewingAvailabilityRequest {self.id} viewing={self.viewing_id} agent={self.property_agent_id} status={self.status}>"
