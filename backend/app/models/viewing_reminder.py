import uuid
from sqlalchemy import (
    Column,
    String,
    Integer,
    DateTime,
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
    ViewingReminderParty,
    ViewingReminderType,
    ViewingReminderStatus,
)


class ViewingReminder(Base):
    __tablename__ = "viewing_reminders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    viewing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("viewings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    party = Column(
        SAEnum(ViewingReminderParty, name="viewing_reminder_party_enum"),
        nullable=False,
    )
    reminder_type = Column(
        SAEnum(ViewingReminderType, name="viewing_reminder_type_enum"),
        nullable=False,
        default=ViewingReminderType.UPCOMING_VIEWING,
    )
    offset_minutes = Column(Integer, nullable=True)
    booking_version = Column(Integer, nullable=False, default=1)

    scheduled_for = Column(DateTime(timezone=True), nullable=False, index=True)
    timezone = Column(String(50), nullable=False, default="Asia/Singapore")

    status = Column(
        SAEnum(ViewingReminderStatus, name="viewing_reminder_status_enum"),
        nullable=False,
        default=ViewingReminderStatus.PENDING,
        index=True,
    )

    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    provider_message_id = Column(String(255), nullable=True)

    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)

    idempotency_key = Column(String(255), unique=True, index=True, nullable=False)

    sent_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    viewing = relationship("Viewing", back_populates="reminders")
    message = relationship("WhatsAppMessage")

    def __repr__(self) -> str:
        return (
            f"<ViewingReminder {self.id} viewing={self.viewing_id} party={self.party} "
            f"status={self.status} scheduled_for={self.scheduled_for}>"
        )


class ViewingScheduleHistory(Base):
    __tablename__ = "viewing_schedule_histories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    viewing_id = Column(
        UUID(as_uuid=True),
        ForeignKey("viewings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    version = Column(Integer, nullable=False)
    scheduled_start_at = Column(DateTime(timezone=True), nullable=True)
    scheduled_end_at = Column(DateTime(timezone=True), nullable=True)
    slot_id = Column(
        UUID(as_uuid=True),
        ForeignKey("viewing_slots.id", ondelete="SET NULL"),
        nullable=True,
    )

    changed_by = Column(String(50), nullable=False)  # TENANT, PROPERTY_AGENT, OPERATOR, SYSTEM
    reason = Column(String(500), nullable=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Relationships
    viewing = relationship("Viewing", back_populates="schedule_history")
    slot = relationship("ViewingSlot")

    def __repr__(self) -> str:
        return (
            f"<ViewingScheduleHistory {self.id} viewing={self.viewing_id} version={self.version} "
            f"changed_by={self.changed_by}>"
        )
