"""
Viewing Reschedule Service - Module 5 Phase 6
Handles viewing reschedule requests from Tenants, Property Agents, and Operators.
Preserves historical booking records, cancels obsolete reminders, increments schedule version,
and re-opens the existing Phase 3/4/5 scheduling workflow.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.viewing_reminder import ViewingScheduleHistory
from app.models.property_agent import PropertyAgent
from app.models.lead import Lead
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingSlotStatus,
    ViewingConfirmationStatus,
    ViewingEventType,
    ViewingActorType,
    ViewingRescheduleRequester,
)
from app.services.viewing_state_machine import ViewingStateMachine
from app.services.viewing_reminder_service import ViewingReminderService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class ViewingRescheduleService:
    """
    Coordinates safe viewing rescheduling without creating separate scheduling logic:
    - Re-validates viewing state (must be CONFIRMED)
    - Captures requester & reason
    - Preserves previous booking in ViewingScheduleHistory
    - Cancels old reminders
    - Releases / un-books previous slot
    - Increments schedule_version
    - Routes viewing back into Phase 3/4/5 scheduling flow
    """

    def __init__(self, db: Session, wa_service: Optional[WhatsAppService] = None):
        self.db = db
        self.whatsapp_service = wa_service or WhatsAppService(db)
        self.reminder_service = ViewingReminderService(db, self.whatsapp_service)

    def request_reschedule(
        self,
        viewing_id: uuid.UUID,
        requested_by: str = "TENANT",  # TENANT, PROPERTY_AGENT, OPERATOR
        reason: Optional[str] = None,
        candidate_slot_start: Optional[datetime] = None,
        candidate_slot_end: Optional[datetime] = None,
        actor_id: str = "system",
        idempotency_token: Optional[str] = None,
    ) -> Viewing:
        """
        Initiates a reschedule workflow on a confirmed viewing.
        Enforces idempotency and validates state machine constraints.
        """
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing '{viewing_id}' not found.")

        # Idempotency check: if viewing is already in an active reschedule workflow, return it safely
        if viewing.status in [
            ViewingStatus.RESCHEDULE_REQUESTED,
            ViewingStatus.AWAITING_AGENT_AVAILABILITY,
            ViewingStatus.AWAITING_TENANT_AVAILABILITY,
            ViewingStatus.SLOTS_AVAILABLE,
        ] and (viewing.reschedule_count or 0) > 0:
            logger.info(f"Viewing {viewing.id} is already in a reschedule workflow, returning idempotently.")
            return viewing

        # Entry conditions
        if viewing.status not in [ViewingStatus.CONFIRMED, ViewingStatus.NO_SHOW]:
            raise ValueError(
                f"Cannot request reschedule for viewing in status '{viewing.status.value}'. Viewing must be CONFIRMED."
            )

        # 1. Locate current booked slot to preserve in history
        booked_slot = (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing.id,
                ViewingSlot.status == ViewingSlotStatus.BOOKED,
            )
            .first()
        )

        current_version = viewing.schedule_version or 1
        old_status = viewing.status.value

        # 2. Preserve old booking snapshot in ViewingScheduleHistory
        history_entry = ViewingScheduleHistory(
            viewing_id=viewing.id,
            version=current_version,
            scheduled_start_at=viewing.scheduled_start_at,
            scheduled_end_at=viewing.scheduled_end_at,
            slot_id=booked_slot.id if booked_slot else None,
            changed_by=requested_by.upper(),
            reason=reason or f"Reschedule requested by {requested_by}",
        )
        self.db.add(history_entry)

        # 3. Cancel all pending reminders for this version
        self.reminder_service.cancel_pending_reminders(
            viewing_id=viewing.id,
            reason=f"Reschedule requested by {requested_by}: {reason or 'Schedule change'}",
            actor_id=actor_id,
        )

        # 4. Release/demote previous booked slot
        if booked_slot:
            booked_slot.status = ViewingSlotStatus.AVAILABLE
            booked_slot.is_mutual_match = False
            self.db.add(booked_slot)

        # 5. Update viewing state & increment schedule_version
        viewing.previous_scheduled_start_at = viewing.scheduled_start_at
        viewing.previous_scheduled_end_at = viewing.scheduled_end_at
        viewing.reschedule_count += 1
        viewing.reschedule_reason = reason
        viewing.schedule_version = current_version + 1

        # Clear scheduled timestamps for the new version until reconfirmed
        viewing.scheduled_start_at = None
        viewing.scheduled_end_at = None
        viewing.tenant_confirmation_status = ViewingConfirmationStatus.PENDING
        viewing.agent_confirmation_status = ViewingConfirmationStatus.PENDING

        # Transition to RESCHEDULE_REQUESTED
        ViewingStateMachine.validate_transition(viewing.status, ViewingStatus.RESCHEDULE_REQUESTED)
        viewing.status = ViewingStatus.RESCHEDULE_REQUESTED

        # 6. Audit & ViewingEvent
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.RESCHEDULE_REQUESTED,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=(
                ViewingActorType.TENANT
                if requested_by.upper() == "TENANT"
                else ViewingActorType.PROPERTY_AGENT
                if requested_by.upper() in ["PROPERTY_AGENT", "AGENT"]
                else ViewingActorType.OPERATOR
            ),
            actor_id=actor_id,
            event_metadata={
                "requested_by": requested_by.upper(),
                "reason": reason,
                "previous_version": current_version,
                "new_version": viewing.schedule_version,
                "previous_start_at": viewing.previous_scheduled_start_at.isoformat() if viewing.previous_scheduled_start_at else None,
            },
        )
        self.db.add(event)

        audit = AuditLog(
            action="VIEWING_RESCHEDULE_REQUESTED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            old_value={
                "status": old_status,
                "version": current_version,
                "scheduled_start_at": viewing.previous_scheduled_start_at.isoformat() if viewing.previous_scheduled_start_at else None,
            },
            new_value={
                "status": viewing.status.value,
                "version": viewing.schedule_version,
                "requested_by": requested_by.upper(),
                "reason": reason,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(viewing)

        # 7. Route into scheduling flow
        self._route_into_scheduling_flow(
            viewing=viewing,
            requested_by=requested_by.upper(),
            candidate_slot_start=candidate_slot_start,
            candidate_slot_end=candidate_slot_end,
            actor_id=actor_id,
        )

        return viewing

    def _route_into_scheduling_flow(
        self,
        viewing: Viewing,
        requested_by: str,
        candidate_slot_start: Optional[datetime] = None,
        candidate_slot_end: Optional[datetime] = None,
        actor_id: str = "system",
    ) -> None:
        """
        Re-enters the Phase 3/4/5 scheduling pipeline based on requester.
        """
        # If agent proposed a specific new slot during reschedule request:
        if candidate_slot_start and requested_by in ["PROPERTY_AGENT", "AGENT", "OPERATOR"]:
            from app.models.enums import ViewingSlotSource
            new_slot = ViewingSlot(
                viewing_id=viewing.id,
                source=ViewingSlotSource.PROPERTY_AGENT if requested_by != "OPERATOR" else ViewingSlotSource.HUMAN_OPERATOR,
                start_at=candidate_slot_start,
                end_at=candidate_slot_end,
                timezone=viewing.timezone or "Asia/Singapore",
                status=ViewingSlotStatus.AVAILABLE,
            )
            self.db.add(new_slot)
            viewing.status = ViewingStatus.SLOTS_AVAILABLE
            self.db.commit()
            return

        # Check existing available slots for this viewing
        available_slots = (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing.id,
                ViewingSlot.status == ViewingSlotStatus.AVAILABLE,
            )
            .all()
        )

        if available_slots:
            # We already have alternative candidate slots available
            if requested_by == "TENANT":
                viewing.status = ViewingStatus.AWAITING_TENANT_AVAILABILITY
            else:
                viewing.status = ViewingStatus.SLOTS_AVAILABLE
        else:
            # Need new availability from agent
            viewing.status = ViewingStatus.AWAITING_AGENT_AVAILABILITY

        self.db.commit()
        self.db.refresh(viewing)

    def get_schedule_history(self, viewing_id: uuid.UUID) -> List[ViewingScheduleHistory]:
        """
        Returns full versioned schedule history for a viewing.
        """
        return (
            self.db.query(ViewingScheduleHistory)
            .filter(ViewingScheduleHistory.viewing_id == viewing_id)
            .order_by(ViewingScheduleHistory.version.asc())
            .all()
        )
