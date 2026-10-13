"""
Viewing Cancellation Service - Module 5 Phase 6
Handles viewing cancellations across all parties (Tenant, Agent, Operator, System).
Cancels active slots, terminates pending reminders, dispatches cancellation notifications,
and enforces strict idempotency against duplicate webhooks and race conditions.
"""
import uuid
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.lead import Lead
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.whatsapp import WhatsAppProfile
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingActorType,
    ViewingCancellationReasonCode,
    ViewingCancellationParty,
)
from app.services.viewing_state_machine import ViewingStateMachine
from app.services.viewing_reminder_service import ViewingReminderService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class ViewingCancellationService:
    """
    Authoritative service governing viewing cancellation:
    - Cancels active slots and stops future automation
    - Terminates all pending/queued reminders
    - Sends WhatsApp cancellation notifications to relevant parties
    - Enforces idempotent execution (subsequent calls return cleanly without re-notifying)
    - Records comprehensive audit trail
    """

    def __init__(self, db: Session, wa_service: Optional[WhatsAppService] = None):
        self.db = db
        self.whatsapp_service = wa_service or WhatsAppService(db)
        self.reminder_service = ViewingReminderService(db, self.whatsapp_service)

    def _get_active_whatsapp_profile(self, lead: Optional[Lead] = None) -> Optional[WhatsAppProfile]:
        if lead and lead.assigned_whatsapp_profile_id:
            profile = self.db.query(WhatsAppProfile).filter(WhatsAppProfile.id == lead.assigned_whatsapp_profile_id).first()
            if profile:
                return profile
        return self.db.query(WhatsAppProfile).first()

    def cancel_viewing(
        self,
        viewing_id: uuid.UUID,
        cancelling_party: str = "TENANT",  # TENANT, PROPERTY_AGENT, OPERATOR, SYSTEM
        reason_code: str = "TENANT_REQUEST",
        reason_text: Optional[str] = None,
        actor_id: str = "system",
        notify_parties: bool = True,
    ) -> Viewing:
        """
        Cancels a viewing safely and idempotently.
        """
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing '{viewing_id}' not found.")

        # Idempotency check: if already cancelled, return existing without re-notifying
        if viewing.status == ViewingStatus.CANCELLED:
            logger.info(f"Viewing {viewing.id} is already CANCELLED. Returning idempotently.")
            return viewing

        if viewing.status == ViewingStatus.COMPLETED:
            raise ValueError("Cannot cancel an already COMPLETED viewing.")

        old_status = viewing.status.value
        now_utc = datetime.now(timezone.utc)
        normalized_party = cancelling_party.upper()
        if normalized_party in ["AGENT", "PROPERTYAGENT"]:
            normalized_party = "PROPERTY_AGENT"
        elif normalized_party in ["HUMAN_OPERATOR", "ADMIN"]:
            normalized_party = "OPERATOR"

        # 1. Update Viewing fields
        combined_reason = f"{reason_code}: {reason_text}" if reason_text else reason_code
        viewing.cancelled_at = now_utc
        viewing.cancelled_by = normalized_party
        viewing.cancellation_reason = combined_reason

        ViewingStateMachine.validate_transition(viewing.status, ViewingStatus.CANCELLED)
        viewing.status = ViewingStatus.CANCELLED

        # 2. Cancel active viewing slots
        for slot in viewing.slots:
            if slot.status in [ViewingSlotStatus.BOOKED, ViewingSlotStatus.SELECTED, ViewingSlotStatus.PROPOSED, ViewingSlotStatus.AVAILABLE]:
                slot.status = ViewingSlotStatus.CANCELLED
                self.db.add(slot)

        # 3. Terminate pending reminders
        self.reminder_service.cancel_pending_reminders(
            viewing_id=viewing.id,
            reason=f"Viewing cancelled by {normalized_party} ({reason_code})",
            actor_id=actor_id,
        )

        # 4. ViewingEvent & AuditLog
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.VIEWING_CANCELLED,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=(
                ViewingActorType.TENANT
                if normalized_party == "TENANT"
                else ViewingActorType.PROPERTY_AGENT
                if normalized_party == "PROPERTY_AGENT"
                else ViewingActorType.OPERATOR
                if normalized_party == "OPERATOR"
                else ViewingActorType.SYSTEM
            ),
            actor_id=actor_id,
            event_metadata={
                "cancelling_party": normalized_party,
                "reason_code": reason_code,
                "reason_text": reason_text,
                "schedule_version": viewing.schedule_version,
            },
        )
        self.db.add(event)

        audit = AuditLog(
            action="VIEWING_CANCELLED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            old_value={"status": old_status},
            new_value={
                "status": viewing.status.value,
                "cancelling_party": normalized_party,
                "reason_code": reason_code,
                "reason_text": reason_text,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(viewing)

        # 5. Send cancellation WhatsApp notifications
        if notify_parties:
            self._send_cancellation_notifications(
                viewing=viewing,
                cancelling_party=normalized_party,
                reason_code=reason_code,
                reason_text=reason_text,
            )

        return viewing

    def _send_cancellation_notifications(
        self,
        viewing: Viewing,
        cancelling_party: str,
        reason_code: str,
        reason_text: Optional[str],
    ) -> None:
        """
        Dispatches cancellation notifications with deterministic idempotency keys.
        """
        prop = viewing.property
        listing = viewing.listing
        lead = viewing.lead
        agent = viewing.property_agent

        prop_title = getattr(prop, "canonical_name", None) or getattr(prop, "building_name", None) or "the property"
        listing_ref = getattr(listing, "listing_reference", None) or getattr(listing, "source_listing_id", None) or "N/A"

        start_dt = viewing.scheduled_start_at or viewing.previous_scheduled_start_at
        if start_dt:
            date_str = start_dt.strftime("%d %b")
            time_str = start_dt.strftime("%I:%M %p")
        else:
            date_str = "scheduled date"
            time_str = "scheduled time"

        version = viewing.schedule_version or 1
        profile = self._get_active_whatsapp_profile(lead)
        if not profile:
            logger.warning("No active WhatsApp profile for sending cancellation notices.")
            return

        reason_display = "property is no longer available" if reason_code == "PROPERTY_UNAVAILABLE" else (reason_text or reason_code.replace("_", " ").lower())

        # Determine notification recipients based on who cancelled
        notify_tenant = False
        notify_agent = False
        tenant_msg = ""
        agent_msg = ""

        if cancelling_party == "TENANT":
            # Tenant initiated: confirm to tenant and notify agent
            notify_tenant = True
            tenant_msg = f"Your viewing for {prop_title} on {date_str} at {time_str} has been cancelled."
            notify_agent = True
            agent_msg = f"The viewing for listing {listing_ref} on {date_str} at {time_str} has been cancelled by the tenant."

        elif cancelling_party == "PROPERTY_AGENT":
            # Agent initiated: notify tenant and confirm to agent
            notify_tenant = True
            tenant_msg = f"Your viewing for {prop_title} on {date_str} at {time_str} has been cancelled by the property agent."
            notify_agent = True
            agent_msg = f"The viewing for listing {listing_ref} on {date_str} at {time_str} has been cancelled."

        elif cancelling_party == "SYSTEM" and reason_code == "PROPERTY_UNAVAILABLE":
            # System cancelled because property is unavailable: notify both
            notify_tenant = True
            tenant_msg = f"Your viewing for {prop_title} on {date_str} at {time_str} has been cancelled as the property is no longer available."
            notify_agent = True
            agent_msg = f"The viewing for listing {listing_ref} on {date_str} at {time_str} has been cancelled (property no longer available)."

        else:
            # Operator or generic system cancellation: notify both
            notify_tenant = True
            tenant_msg = f"Your viewing for {prop_title} on {date_str} at {time_str} has been cancelled ({reason_display})."
            notify_agent = True
            agent_msg = f"The viewing for listing {listing_ref} on {date_str} at {time_str} has been cancelled ({reason_display})."

        # Dispatch tenant notice
        if notify_tenant and lead and (lead.phone_normalized or lead.phone):
            t_key = f"viewing:{viewing.id}:cancellation-notice:tenant:{version}"
            try:
                self.whatsapp_service.send_message(
                    profile_id=profile.id,
                    recipient=lead.phone_normalized or lead.phone,
                    content=tenant_msg,
                    idempotency_key=t_key,
                )
            except Exception as e:
                logger.warning(f"Could not dispatch tenant cancellation notification: {e}")

        # Dispatch agent notice
        if notify_agent and agent and (agent.phone_normalized or agent.phone):
            a_key = f"viewing:{viewing.id}:cancellation-notice:agent:{version}"
            try:
                self.whatsapp_service.send_message(
                    profile_id=profile.id,
                    recipient=agent.phone_normalized or agent.phone,
                    content=agent_msg,
                    idempotency_key=a_key,
                )
            except Exception as e:
                logger.warning(f"Could not dispatch agent cancellation notification: {e}")
