import uuid
from sqlalchemy import (
    Column,
    String,
    Text,
    Numeric,
    DateTime,
    ForeignKey,
    Enum as SAEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import PropertyInterestStatus, TenantInterestIntent


class PropertyInterest(Base):
    __tablename__ = "property_interests"
    __table_args__ = (
        UniqueConstraint("lead_id", "property_match_id", name="uq_lead_property_match_interest"),
    )

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
    shortlist_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_shortlists.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shortlist_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_shortlist_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    viewing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("viewings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        SAEnum(PropertyInterestStatus, name="property_interest_status_enum", native_enum=True),
        nullable=False,
        default=PropertyInterestStatus.NOT_PRESENTED,
        index=True,
    )

    source_message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
    )

    presented_at = Column(DateTime(timezone=True), nullable=True)
    responded_at = Column(DateTime(timezone=True), nullable=True)

    # Snapshot of what was shown to tenant
    presented_price = Column(Numeric(12, 2), nullable=True)
    presented_currency = Column(String(10), nullable=False, default="SGD")
    presented_availability = Column(String(100), nullable=True)
    presentation_notes = Column(Text, nullable=True)

    # Inbound response understanding metadata
    last_intent = Column(
        SAEnum(TenantInterestIntent, name="tenant_interest_intent_enum", native_enum=True),
        nullable=True,
    )
    tenant_notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    lead = relationship("Lead")
    property_match = relationship("PropertyMatch")
    shortlist = relationship("PropertyShortlist")
    shortlist_item = relationship("PropertyShortlistItem")
    viewing = relationship("Viewing")
    source_message = relationship("WhatsAppMessage")

    def __repr__(self) -> str:
        return f"<PropertyInterest {self.id} lead={self.lead_id} match={self.property_match_id} status={self.status}>"
