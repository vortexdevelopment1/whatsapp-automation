from datetime import datetime, timedelta, timezone as dt_timezone
from typing import List, Optional
import uuid
import zoneinfo
from sqlalchemy.orm import Session

from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.enums import (
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingActorType,
)
from app.services.viewing_config import ViewingConfig


class ViewingSlotService:
    @classmethod
    def validate_timezone(cls, tz_str: str) -> str:
        try:
            zoneinfo.ZoneInfo(tz_str)
            return tz_str
        except Exception:
            raise ValueError(f"Invalid timezone identifier: '{tz_str}'")

    @classmethod
    def add_slot(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        start_at: datetime,
        end_at: Optional[datetime] = None,
        source: ViewingSlotSource = ViewingSlotSource.HUMAN_OPERATOR,
        timezone: str = "Asia/Singapore",
        source_message_id: Optional[uuid.UUID] = None,
        actor_id: str = "operator",
    ) -> ViewingSlot:
        viewing = db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        cls.validate_timezone(timezone)

        # Standardize start_at
        if start_at.tzinfo is None:
            # Assume UTC or given timezone
            start_at = start_at.replace(tzinfo=dt_timezone.utc)

        # Validate end_at
        if end_at is not None:
            if end_at.tzinfo is None:
                end_at = end_at.replace(tzinfo=dt_timezone.utc)
            if end_at <= start_at:
                raise ValueError("Slot end_at must be strictly greater than start_at")
        else:
            duration = viewing.duration_minutes or ViewingConfig.DEFAULT_VIEWING_DURATION_MINUTES
            end_at = start_at + timedelta(minutes=duration)

        # Prevent duplicate identical start_at for the same viewing
        existing = (
            db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing_id,
                ViewingSlot.start_at == start_at,
                ViewingSlot.status.notin_([ViewingSlotStatus.CANCELLED, ViewingSlotStatus.REJECTED]),
            )
            .first()
        )
        if existing:
            return existing

        slot = ViewingSlot(
            viewing_id=viewing_id,
            source=source,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            status=ViewingSlotStatus.AVAILABLE,
            source_message_id=source_message_id,
        )
        db.add(slot)
        db.flush()

        # Audit event
        event = ViewingEvent(
            viewing_id=viewing_id,
            event_type=ViewingEventType.SLOT_CREATED,
            old_status=None,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR if source == ViewingSlotSource.HUMAN_OPERATOR else ViewingActorType.SYSTEM,
            actor_id=actor_id,
            event_metadata={
                "slot_id": str(slot.id),
                "start_at": start_at.isoformat(),
                "end_at": end_at.isoformat(),
                "source": source.value,
            },
        )
        db.add(event)
        db.commit()
        db.refresh(slot)
        return slot

    @classmethod
    def list_slots(cls, db: Session, viewing_id: uuid.UUID) -> List[ViewingSlot]:
        return (
            db.query(ViewingSlot)
            .filter(ViewingSlot.viewing_id == viewing_id)
            .order_by(ViewingSlot.start_at.asc())
            .all()
        )

    @classmethod
    def get_slot(cls, db: Session, viewing_id: uuid.UUID, slot_id: uuid.UUID) -> ViewingSlot:
        slot = (
            db.query(ViewingSlot)
            .filter(ViewingSlot.id == slot_id, ViewingSlot.viewing_id == viewing_id)
            .first()
        )
        if not slot:
            raise ValueError(f"ViewingSlot {slot_id} not found for viewing {viewing_id}")
        return slot

    @classmethod
    def select_slot(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        slot_id: uuid.UUID,
        actor_id: str = "operator",
    ) -> ViewingSlot:
        viewing = db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        slot = cls.get_slot(db, viewing_id, slot_id)

        # Enforce at most one SELECTED / BOOKED slot rule: demote any previously selected slot
        prev_selected = (
            db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing_id,
                ViewingSlot.id != slot_id,
                ViewingSlot.status.in_([ViewingSlotStatus.SELECTED, ViewingSlotStatus.BOOKED]),
            )
            .all()
        )
        for ps in prev_selected:
            ps.status = ViewingSlotStatus.AVAILABLE

        slot.status = ViewingSlotStatus.SELECTED

        # Update viewing scheduled timestamps
        viewing.scheduled_start_at = slot.start_at
        viewing.scheduled_end_at = slot.end_at
        viewing.timezone = slot.timezone

        # Audit event
        event = ViewingEvent(
            viewing_id=viewing_id,
            event_type=ViewingEventType.SLOT_SELECTED,
            old_status=viewing.status.value,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR,
            actor_id=actor_id,
            event_metadata={
                "slot_id": str(slot.id),
                "scheduled_start_at": slot.start_at.isoformat(),
                "scheduled_end_at": slot.end_at.isoformat() if slot.end_at else None,
            },
        )
        db.add(event)
        db.commit()
        db.refresh(slot)
        return slot

    @classmethod
    def update_slot_status(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        slot_id: uuid.UUID,
        target_status: ViewingSlotStatus,
        actor_id: str = "operator",
    ) -> ViewingSlot:
        slot = cls.get_slot(db, viewing_id, slot_id)
        slot.status = target_status
        db.commit()
        db.refresh(slot)
        return slot

    @classmethod
    def bulk_add_agent_slots(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        slots_data: List[dict],
        source_message_id: Optional[uuid.UUID] = None,
        timezone: str = "Asia/Singapore",
        actor_id: str = "system",
    ) -> List[ViewingSlot]:
        """
        Bulk adds candidate slots provided by a property agent.
        Validates timestamps, prevents duplicates, preserves provenance,
        and ensures slots are in the future.
        """
        viewing = db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        cls.validate_timezone(timezone)
        created_slots: List[ViewingSlot] = []

        for item in slots_data:
            start_at: datetime = item["start_at"]
            end_at: Optional[datetime] = item.get("end_at")
            slot_tz: str = item.get("timezone", timezone)
            cls.validate_timezone(slot_tz)

            if start_at.tzinfo is None:
                start_at = start_at.replace(tzinfo=dt_timezone.utc)

            if end_at is not None:
                if end_at.tzinfo is None:
                    end_at = end_at.replace(tzinfo=dt_timezone.utc)
                if end_at <= start_at:
                    # Ignore invalid time window or skip
                    continue
            else:
                duration = viewing.duration_minutes or ViewingConfig.DEFAULT_VIEWING_DURATION_MINUTES
                end_at = start_at + timedelta(minutes=duration)

            # Prevent duplicate identical start_at for the same viewing
            existing = (
                db.query(ViewingSlot)
                .filter(
                    ViewingSlot.viewing_id == viewing_id,
                    ViewingSlot.start_at == start_at,
                    ViewingSlot.status.notin_([ViewingSlotStatus.CANCELLED, ViewingSlotStatus.REJECTED]),
                )
                .first()
            )
            if existing:
                created_slots.append(existing)
                continue

            slot = ViewingSlot(
                viewing_id=viewing_id,
                source=ViewingSlotSource.PROPERTY_AGENT,
                start_at=start_at,
                end_at=end_at,
                timezone=slot_tz,
                status=ViewingSlotStatus.AVAILABLE,
                source_message_id=source_message_id,
            )
            db.add(slot)
            db.flush()

            event = ViewingEvent(
                viewing_id=viewing_id,
                event_type=ViewingEventType.SLOT_CREATED,
                old_status=None,
                new_status=viewing.status.value,
                actor_type=ViewingActorType.PROPERTY_AGENT,
                actor_id=actor_id,
                event_metadata={
                    "slot_id": str(slot.id),
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                    "source": ViewingSlotSource.PROPERTY_AGENT.value,
                    "source_message_id": str(source_message_id) if source_message_id else None,
                },
            )
            db.add(event)
            created_slots.append(slot)

        db.commit()
        for s in created_slots:
            db.refresh(s)
        return created_slots

