import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class PropertyAgentConversation(Base):
    __tablename__ = "property_agent_conversations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_agents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
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

    conversation_type = Column(String(50), nullable=False, default="PROPERTY_AGENT", index=True)
    status = Column(String(50), nullable=False, default="ACTIVE", index=True)
    reference_code = Column(String(100), nullable=True, index=True)
    last_message_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    property_agent = relationship("PropertyAgent")
    lead = relationship("Lead")
    property = relationship("Property")
    listing = relationship("PropertyListing")
    property_match = relationship("PropertyMatch")
    outreach_records = relationship(
        "PropertyAgentOutreach",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="desc(PropertyAgentOutreach.created_at)",
    )
