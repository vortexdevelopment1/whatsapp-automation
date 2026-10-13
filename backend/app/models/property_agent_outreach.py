import uuid
from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertyAgentOutreachType, PropertyAgentOutreachStatus


class PropertyAgentOutreach(Base):
    __tablename__ = "property_agent_outreach"

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
    property_match_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_matches.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    property_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    conversation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agent_conversations.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    whatsapp_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    template_id = Column(
        UUID(as_uuid=True),
        ForeignKey("message_templates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    outreach_type = Column(
        SAEnum(PropertyAgentOutreachType, name="property_agent_outreach_type_enum"),
        nullable=False,
        default=PropertyAgentOutreachType.INITIAL_AVAILABILITY_CHECK,
    )
    status = Column(
        SAEnum(PropertyAgentOutreachStatus, name="property_agent_outreach_status_enum"),
        nullable=False,
        default=PropertyAgentOutreachStatus.PENDING,
        index=True,
    )

    provider_message_id = Column(String(255), nullable=True, index=True)
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    reference_code = Column(String(100), nullable=True, index=True)
    recipient_phone = Column(String(50), nullable=True)
    message_content = Column(Text, nullable=True)

    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    replied_at = Column(DateTime(timezone=True), nullable=True)
    response_due_at = Column(DateTime(timezone=True), nullable=True)
    followup_attempt = Column(Integer, nullable=False, default=0)

    error_code = Column(String(100), nullable=True)
    error_message = Column(Text, nullable=True)
    extra_metadata = Column("metadata", JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    lead = relationship("Lead")
    property = relationship("Property")
    listing = relationship("PropertyListing")
    property_match = relationship("PropertyMatch", back_populates="outreach_records")
    property_agent = relationship("PropertyAgent")
    conversation = relationship("PropertyAgentConversation", back_populates="outreach_records")
    whatsapp_message = relationship("WhatsAppMessage")
    template = relationship("MessageTemplate")
