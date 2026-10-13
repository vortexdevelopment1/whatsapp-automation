import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PropertyAgentFollowUp(Base):
    __tablename__ = "property_agent_followups"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
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
        ForeignKey("property_listings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    property_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    outreach_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agent_outreach.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agent_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    followup_type = Column(String(50), nullable=False, default="NUDGE", index=True)
    attempt_number = Column(Integer, nullable=False, default=1)
    status = Column(String(50), nullable=False, default="PENDING", index=True)

    due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(String(255), nullable=True)

    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    message_content = Column(Text, nullable=True)

    whatsapp_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    lead = relationship("Lead")
    property_match = relationship("PropertyMatch", back_populates="followup_records")
    listing = relationship("PropertyListing")
    property_agent = relationship("PropertyAgent")
    outreach = relationship("PropertyAgentOutreach", backref="followups")
    conversation = relationship("PropertyAgentConversation")
    whatsapp_message = relationship("WhatsAppMessage")
