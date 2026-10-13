import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
    Boolean,
    ForeignKey,
    Text,
    Enum as SAEnum,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base
from app.models.enums import (
    ViewingStatus,
    ViewingConfirmationStatus,
    ViewingLocationType,
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingActorType,
)


class Viewing(Base):
    __tablename__ = "viewings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("leads.id", ondelete="CASCADE"),
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
    property_match_id = Column(
        UUID(as_uuid=True),
        ForeignKey("property_matches.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    property_id = Column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="RESTRICT"),
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

    status = Column(
        SAEnum(ViewingStatus, name="viewing_status_enum"),
        nullable=False,
        default=ViewingStatus.DRAFT,
        index=True,
    )

    scheduled_start_at = Column(DateTime(timezone=True), nullable=True, index=True)
    scheduled_end_at = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String(50), nullable=False, default="Asia/Singapore")
    duration_minutes = Column(Integer, nullable=False, default=30)

    location_type = Column(
        SAEnum(ViewingLocationType, name="viewing_location_type_enum"),
        nullable=False,
        default=ViewingLocationType.IN_PERSON,
    )
    location_text = Column(String(500), nullable=True)
    meeting_url = Column(String(1024), nullable=True)

    tenant_confirmation_status = Column(
        SAEnum(ViewingConfirmationStatus, name="viewing_confirmation_status_enum"),
        nullable=False,
        default=ViewingConfirmationStatus.NOT_REQUIRED,
    )
    agent_confirmation_status = Column(
        SAEnum(ViewingConfirmationStatus, name="viewing_agent_confirmation_status_enum"),
        nullable=False,
        default=ViewingConfirmationStatus.NOT_REQUIRED,
    )

    schedule_version = Column(Integer, nullable=False, default=1)
    reschedule_count = Column(Integer, nullable=False, default=0)
    previous_scheduled_start_at = Column(DateTime(timezone=True), nullable=True)
    previous_scheduled_end_at = Column(DateTime(timezone=True), nullable=True)
    reschedule_reason = Column(String(500), nullable=True)

    cancellation_reason = Column(String(500), nullable=True)
    cancelled_by = Column(String(50), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    completed_at = Column(DateTime(timezone=True), nullable=True)
    outcome = Column(String(50), nullable=True)
    outcome_notes = Column(Text, nullable=True)

    created_by = Column(String(100), nullable=False, default="system")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    lead = relationship("Lead")
    shortlist = relationship("PropertyShortlist")
    shortlist_item = relationship("PropertyShortlistItem")
    property_match = relationship("PropertyMatch")
    property = relationship("Property")
    listing = relationship("PropertyListing")
    property_agent = relationship("PropertyAgent")

    slots = relationship(
        "ViewingSlot",
        back_populates="viewing",
        cascade="all, delete-orphan",
        order_by="ViewingSlot.start_at",
    )
    events = relationship(
        "ViewingEvent",
        back_populates="viewing",
        cascade="all, delete-orphan",
        order_by="ViewingEvent.created_at.desc()",
    )
    reminders = relationship(
        "ViewingReminder",
        back_populates="viewing",
        cascade="all, delete-orphan",
        order_by="ViewingReminder.scheduled_for",
    )
    schedule_history = relationship(
        "ViewingScheduleHistory",
        back_populates="viewing",
        cascade="all, delete-orphan",
        order_by="ViewingScheduleHistory.created_at.desc()",
    )

    def __repr__(self) -> str:
        return f"<Viewing {self.id} lead={self.lead_id} match={self.property_match_id} status={self.status}>"


class ViewingSlot(Base):
    __tablename__ = "viewing_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    viewing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("viewings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    source = Column(
        SAEnum(ViewingSlotSource, name="viewing_slot_source_enum"),
        nullable=False,
    )
    start_at = Column(DateTime(timezone=True), nullable=False, index=True)
    end_at = Column(DateTime(timezone=True), nullable=True)
    timezone = Column(String(50), nullable=False, default="Asia/Singapore")

    status = Column(
        SAEnum(ViewingSlotStatus, name="viewing_slot_status_enum"),
        nullable=False,
        default=ViewingSlotStatus.AVAILABLE,
        index=True,
    )
    source_message_id = Column(UUID(as_uuid=True), nullable=True)
    is_mutual_match = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    viewing = relationship("Viewing", back_populates="slots")

    def __repr__(self) -> str:
        return f"<ViewingSlot {self.id} viewing={self.viewing_id} start={self.start_at} status={self.status}>"


class ViewingEvent(Base):
    __tablename__ = "viewing_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    viewing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("viewings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    event_type = Column(
        SAEnum(ViewingEventType, name="viewing_event_type_enum"),
        nullable=False,
        index=True,
    )
    old_status = Column(String(50), nullable=True)
    new_status = Column(String(50), nullable=True)

    actor_type = Column(
        SAEnum(ViewingActorType, name="viewing_actor_type_enum"),
        nullable=False,
        default=ViewingActorType.SYSTEM,
    )
    actor_id = Column(String(100), nullable=True)
    event_metadata = Column("metadata", JSONB, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    viewing = relationship("Viewing", back_populates="events")

    def __repr__(self) -> str:
        return f"<ViewingEvent {self.id} viewing={self.viewing_id} type={self.event_type}>"
