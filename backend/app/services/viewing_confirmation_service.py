"""
Viewing Confirmation Service - Module 5 Phase 5
Governs the conversion of a proposed viewing slot into a locked, confirmed booking.
Enforces:
- Strict entry revalidation (property, listing, proposed slot, tenant eligibility).
- Separate tracking of tenant and agent confirmation states.
- Configurable confirmation policies and pre-confirmation rules.
- Conflict & double-booking prevention.
- Transactional slot locking (slot -> BOOKED).
- State machine transition to ViewingStatus.CONFIRMED.
- Informative booking confirmation notices to both parties.
- Strict prevention of AI mutating confirmation states directly.
"""
import uuid
import logging
import re
import zoneinfo
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_, and_

from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.lead import Lead
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_match import PropertyMatch
from app.models.property_agent import PropertyAgent
from app.models.property_agent_conversation import PropertyAgentConversation
from app.models.whatsapp import WhatsAppProfile
from app.models.message import WhatsAppMessage
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingConfirmationStatus,
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingActorType,
    TenantConfirmationResponseIntent,
    AgentConfirmationResponseIntent,
    ConfirmationParty,
    PropertyStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
    ContactEligibility,
    MessageDirection,
    MessageType,
    WhatsAppConnectionStatus,
)
from app.schemas.viewing_confirmation import (
    ViewingConfirmationRequestResponse,
    TenantConfirmationUnderstandingResult,
    AgentConfirmationUnderstandingResult,
    ViewingConfirmationStatusOverview,
    ViewingFinalizeBookingResponse,
)
from app.schemas.viewing import ViewingSlotResponse
from app.services.whatsapp_service import WhatsAppService
from app.services.viewing_slot_matching_service import ViewingSlotMatchingService
from app.services.viewing_service import ViewingService
from app.services.viewing_state_machine import ViewingStateMachine
from app.services.viewing_config import ViewingConfig, ViewingConfirmationPolicy

logger = logging.getLogger(__name__)


class ViewingConfirmationService:
    """
    Authoritative coordinator for viewing confirmation and booking finalization.
    """

    def __init__(self, db: Session, whatsapp_service: Optional[WhatsAppService] = None):
        self.db = db
        self.whatsapp_service = whatsapp_service or WhatsAppService(db)
        self.policy: ViewingConfirmationPolicy = ViewingConfig.get_confirmation_policy()

    @staticmethod
    def get_booking_reference(viewing_id: uuid.UUID) -> str:
        """Generates a stable, human-readable booking reference."""
        hex_part = str(viewing_id).replace("-", "").upper()[:8]
        return f"VW-2026-{hex_part}"

    def get_proposed_slot(self, viewing_id: uuid.UUID) -> Optional[ViewingSlot]:
        """Loads the current active proposed or selected slot for the viewing."""
        slot = (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing_id,
                ViewingSlot.status.in_([ViewingSlotStatus.PROPOSED, ViewingSlotStatus.SELECTED]),
            )
            .order_by(desc(ViewingSlot.updated_at))
            .first()
        )
        return slot

    def get_booked_slot(self, viewing_id: uuid.UUID) -> Optional[ViewingSlot]:
        """Loads the booked slot if viewing is confirmed."""
        return (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing_id,
                ViewingSlot.status == ViewingSlotStatus.BOOKED,
            )
            .first()
        )

    def validate_for_confirmation(self, viewing_id: uuid.UUID) -> Dict[str, Any]:
        """
        Comprehensive revalidation of all conditions before proceeding with confirmation or booking:
        - Viewing exists and is active (not CANCELLED, COMPLETED, NO_SHOW, REJECTED)
        - Viewing is in SLOT_PROPOSED or AWAITING_CONFIRMATION
        - Proposed slot exists and is not expired (start_at > now UTC)
        - Property is active
        - Listing is active and available
        - Candidate property match is not stale
        - Lead is eligible and not opted out
        - No conflict with another confirmed viewing for the same tenant
        """
        now_utc = datetime.now(dt_timezone.utc)
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            return {"valid": False, "reason": f"Viewing {viewing_id} not found", "viewing": None}

        if viewing.status in [ViewingStatus.CANCELLED, ViewingStatus.COMPLETED, ViewingStatus.NO_SHOW, ViewingStatus.REJECTED]:
            return {
                "valid": False,
                "reason": f"Viewing {viewing_id} is inactive (status={viewing.status.value}).",
                "viewing": viewing,
            }

        # Check candidate match
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == viewing.property_match_id).first()
        if not match or match.is_stale:
            return {"valid": False, "reason": "Candidate property match is stale or missing.", "viewing": viewing}

        # Check Property & Listing
        prop = self.db.query(Property).filter(Property.id == viewing.property_id).first()
        if not prop or prop.status == PropertyStatus.INACTIVE:
            return {"valid": False, "reason": "Property is inactive or unavailable.", "viewing": viewing}

        listing = self.db.query(PropertyListing).filter(PropertyListing.id == viewing.listing_id).first()
        if (
            not listing
            or listing.listing_status in [PropertyListingStatus.INACTIVE, PropertyListingStatus.REMOVED, PropertyListingStatus.EXPIRED]
            or listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE
        ):
            return {"valid": False, "reason": "Listing is no longer available.", "viewing": viewing}

        # Check Tenant / Lead eligibility
        lead = self.db.query(Lead).filter(Lead.id == viewing.lead_id).first()
        if not lead or lead.contact_eligibility != ContactEligibility.ELIGIBLE:
            return {"valid": False, "reason": "Lead is ineligible or has opted out of contact.", "viewing": viewing}

        # Check proposed slot
        slot = self.get_proposed_slot(viewing_id)
        if not slot and viewing.status != ViewingStatus.CONFIRMED:
            return {"valid": False, "reason": "No active proposed viewing slot found for viewing.", "viewing": viewing}

        if slot:
            slot_start_utc = ViewingSlotMatchingService.to_utc(slot.start_at, slot.timezone)
            if slot_start_utc <= now_utc:
                slot.status = ViewingSlotStatus.EXPIRED
                self.db.commit()
                return {"valid": False, "reason": "The proposed viewing slot has expired.", "viewing": viewing, "slot": slot}

            # Conflict Detection: check if tenant has an overlapping confirmed viewing
            slot_end_utc = ViewingSlotMatchingService.to_utc(
                slot.end_at or (slot.start_at + timedelta(minutes=viewing.duration_minutes or 30)),
                slot.timezone,
            )
            overlapping_confirmed = (
                self.db.query(Viewing)
                .filter(
                    Viewing.lead_id == viewing.lead_id,
                    Viewing.id != viewing.id,
                    Viewing.status == ViewingStatus.CONFIRMED,
                    Viewing.scheduled_start_at < slot_end_utc,
                    Viewing.scheduled_end_at > slot_start_utc,
                )
                .first()
            )
            if overlapping_confirmed:
                return {
                    "valid": False,
                    "reason": f"Tenant has a conflicting confirmed viewing ({overlapping_confirmed.id}) at the same time.",
                    "viewing": viewing,
                    "conflict_viewing": overlapping_confirmed,
                }

        return {
            "valid": True,
            "viewing": viewing,
            "proposed_slot": slot,
            "property": prop,
            "listing": listing,
            "lead": lead,
        }

    def format_slot_display(self, slot: ViewingSlot, viewing: Viewing) -> str:
        """Formats the slot date and time in the display timezone."""
        display_tz = viewing.timezone or slot.timezone or ViewingConfig.DEFAULT_TIMEZONE
        start_local = ViewingSlotMatchingService.to_display_tz(
            ViewingSlotMatchingService.to_utc(slot.start_at, slot.timezone),
            display_tz,
        )
        end_dt = slot.end_at or (slot.start_at + timedelta(minutes=viewing.duration_minutes or 30))
        end_local = ViewingSlotMatchingService.to_display_tz(
            ViewingSlotMatchingService.to_utc(end_dt, slot.timezone),
            display_tz,
        )
        return f"{start_local.strftime('%A, %d %b %Y')} from {start_local.strftime('%I:%M %p')} to {end_local.strftime('%I:%M %p')}"

    def request_tenant_confirmation(
        self,
        viewing_id: uuid.UUID,
        actor_id: str = "operator",
        custom_message: Optional[str] = None,
    ) -> ViewingConfirmationRequestResponse:
        """
        Dispatches final confirmation request to tenant via WhatsApp.
        - Validates entry conditions and proposed slot.
        - Idempotency key: viewing:{viewing_id}:tenant-confirmation:{slot_id}.
        - Transitions viewing to AWAITING_TENANT_CONFIRMATION if currently in SLOT_PROPOSED.
        - Sets tenant_confirmation_status = PENDING.
        """
        validation = self.validate_for_confirmation(viewing_id)
        if not validation["valid"]:
            raise ValueError(f"Cannot request tenant confirmation: {validation['reason']}")

        viewing: Viewing = validation["viewing"]
        slot: ViewingSlot = validation["proposed_slot"]
        lead: Lead = validation["lead"]
        prop: Property = validation["property"]

        # Human takeover check
        is_takeover = getattr(lead, "human_takeover", False) or (
            lead.tenant_requirement and getattr(lead.tenant_requirement, "ai_paused", False)
        )
        if is_takeover:
            raise ValueError("Tenant conversation is under HUMAN_TAKEOVER. Automated confirmation requests paused.")

        idempotency_key = f"viewing:{viewing.id}:tenant-confirmation:{slot.id}"
        prop_title = getattr(prop, "canonical_name", None) or getattr(prop, "building_name", None) or "the property"
        slot_text = self.format_slot_display(slot, viewing)

        if custom_message:
            body_text = custom_message
        else:
            body_text = (
                f"Your viewing for {prop_title} is proposed for:\n\n"
                f"📅 {slot_text}\n\n"
                f"Please reply 'CONFIRM' to finalize your booking, or let us know if you need to choose another time."
            )

        provider_msg_id = None
        message_sent = False
        try:
            profile = lead.assigned_whatsapp_profile or self.db.query(WhatsAppProfile).first()
            if profile and lead.phone_normalized:
                wa_msg = self.whatsapp_service.send_message(
                    profile_id=profile.id,
                    recipient=lead.phone_normalized,
                    content=body_text,
                    idempotency_key=idempotency_key,
                )
                provider_msg_id = wa_msg.provider_message_id
                message_sent = True
        except Exception as e:
            logger.error(f"Failed to dispatch tenant confirmation message: {e}")
            raise RuntimeError(f"WhatsApp dispatch failed: {str(e)}")

        # Update confirmation status
        viewing.tenant_confirmation_status = ViewingConfirmationStatus.PENDING

        # Transition viewing status if in SLOT_PROPOSED
        old_status = viewing.status.value
        if viewing.status == ViewingStatus.SLOT_PROPOSED:
            if ViewingStateMachine.can_transition(viewing.status, ViewingStatus.AWAITING_TENANT_CONFIRMATION):
                viewing.status = ViewingStatus.AWAITING_TENANT_CONFIRMATION

        # Audit event
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.STATUS_CHANGED,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR if actor_id == "operator" else ViewingActorType.SYSTEM,
            actor_id=actor_id,
            event_metadata={
                "action": "TENANT_CONFIRMATION_REQUESTED",
                "slot_id": str(slot.id),
                "idempotency_key": idempotency_key,
                "provider_message_id": provider_msg_id,
            },
        )
        self.db.add(event)

        audit = AuditLog(
            action="TENANT_CONFIRMATION_REQUESTED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={
                "slot_id": str(slot.id),
                "idempotency_key": idempotency_key,
                "provider_message_id": provider_msg_id,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(viewing)

        return ViewingConfirmationRequestResponse(
            viewing_id=viewing.id,
            party=ConfirmationParty.TENANT,
            status=viewing.tenant_confirmation_status,
            message_sent=message_sent,
            provider_message_id=provider_msg_id,
            sent_at=datetime.now(dt_timezone.utc),
            proposed_start_at=slot.start_at,
            proposed_end_at=slot.end_at,
        )

    def request_agent_confirmation(
        self,
        viewing_id: uuid.UUID,
        actor_id: str = "operator",
        custom_message: Optional[str] = None,
    ) -> ViewingConfirmationRequestResponse:
        """
        Dispatches final confirmation request to property agent via WhatsApp.
        - Validates entry conditions and proposed slot.
        - Idempotency key: viewing:{viewing_id}:agent-confirmation:{slot_id}.
        - Transitions viewing to AWAITING_AGENT_CONFIRMATION.
        - Sets agent_confirmation_status = PENDING.
        """
        validation = self.validate_for_confirmation(viewing_id)
        if not validation["valid"]:
            raise ValueError(f"Cannot request agent confirmation: {validation['reason']}")

        viewing: Viewing = validation["viewing"]
        slot: ViewingSlot = validation["proposed_slot"]
        listing: PropertyListing = validation["listing"]
        prop: Property = validation["property"]

        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == viewing.property_agent_id).first()
        if not agent or not agent.phone_normalized:
            raise ValueError("Property agent not found or has no usable phone.")

        idempotency_key = f"viewing:{viewing.id}:agent-confirmation:{slot.id}"
        prop_title = getattr(prop, "canonical_name", None) or getattr(prop, "building_name", None) or "the property"
        listing_ref = listing.listing_reference or listing.source_listing_id or "N/A"
        slot_text = self.format_slot_display(slot, viewing)

        if custom_message:
            body_text = custom_message
        else:
            body_text = (
                f"Viewing Confirmation Request:\n\n"
                f"Tenant has requested to view {prop_title} (Listing Ref: {listing_ref}) on:\n"
                f"📅 {slot_text}\n\n"
                f"Please reply 'CONFIRM' to confirm that this slot is locked and available, or 'DECLINE' if unavailable."
            )

        provider_msg_id = None
        message_sent = False
        try:
            profile = self.db.query(WhatsAppProfile).first()
            if profile and agent.phone_normalized:
                wa_msg = self.whatsapp_service.send_message(
                    profile_id=profile.id,
                    recipient=agent.phone_normalized,
                    content=body_text,
                    idempotency_key=idempotency_key,
                )
                provider_msg_id = wa_msg.provider_message_id
                message_sent = True
        except Exception as e:
            logger.error(f"Failed to dispatch agent confirmation message: {e}")
            raise RuntimeError(f"WhatsApp dispatch failed: {str(e)}")

        # Update confirmation status
        viewing.agent_confirmation_status = ViewingConfirmationStatus.PENDING

        # Transition viewing status if applicable
        old_status = viewing.status.value
        if viewing.status in [ViewingStatus.SLOT_PROPOSED, ViewingStatus.AWAITING_TENANT_CONFIRMATION]:
            if ViewingStateMachine.can_transition(viewing.status, ViewingStatus.AWAITING_AGENT_CONFIRMATION):
                viewing.status = ViewingStatus.AWAITING_AGENT_CONFIRMATION

        # Audit event
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.STATUS_CHANGED,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR if actor_id == "operator" else ViewingActorType.SYSTEM,
            actor_id=actor_id,
            event_metadata={
                "action": "AGENT_CONFIRMATION_REQUESTED",
                "slot_id": str(slot.id),
                "idempotency_key": idempotency_key,
                "provider_message_id": provider_msg_id,
            },
        )
        self.db.add(event)

        audit = AuditLog(
            action="AGENT_CONFIRMATION_REQUESTED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={
                "slot_id": str(slot.id),
                "idempotency_key": idempotency_key,
                "provider_message_id": provider_msg_id,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(viewing)

        return ViewingConfirmationRequestResponse(
            viewing_id=viewing.id,
            party=ConfirmationParty.PROPERTY_AGENT,
            status=viewing.agent_confirmation_status,
            message_sent=message_sent,
            provider_message_id=provider_msg_id,
            sent_at=datetime.now(dt_timezone.utc),
            proposed_start_at=slot.start_at,
            proposed_end_at=slot.end_at,
        )

    def classify_tenant_confirmation_intent(self, text: str, interactive_payload: Optional[Dict[str, Any]] = None) -> TenantConfirmationResponseIntent:
        """Classifies tenant confirmation response intent."""
        # 1. Interactive Button payload
        if interactive_payload:
            btn_id = str(interactive_payload.get("id") or interactive_payload.get("action") or "").lower()
            if "confirm" in btn_id:
                return TenantConfirmationResponseIntent.CONFIRM_VIEWING
            if "change" in btn_id:
                return TenantConfirmationResponseIntent.REQUEST_DIFFERENT_TIME
            if "cancel" in btn_id:
                return TenantConfirmationResponseIntent.CANCEL_VIEWING

        text_lower = text.lower().strip()

        # 2. Cancel
        if any(p in text_lower for p in [
            "cancel", "cancel viewing", "don't want to view anymore", "dont want to view anymore",
            "cancel the appointment", "cancel it", "stop viewing"
        ]):
            return TenantConfirmationResponseIntent.CANCEL_VIEWING

        # 3. Request Different Time / Change
        if any(p in text_lower for p in [
            "change time", "different time", "reschedule", "another time", "cannot make that time",
            "different day", "change date", "can we do another"
        ]):
            return TenantConfirmationResponseIntent.REQUEST_DIFFERENT_TIME

        # 4. Decline
        if any(p in text_lower for p in [
            "no", "decline", "doesn't work", "does not work", "can't make it", "cannot make it",
            "not free", "won't be able to", "wont be able to"
        ]):
            return TenantConfirmationResponseIntent.DECLINE_VIEWING

        # 5. Question
        if any(p in text_lower for p in [
            "where is it", "what's the address", "whats the address", "how much is the rent",
            "where do we meet", "what is the location"
        ]):
            return TenantConfirmationResponseIntent.ASK_VIEWING_QUESTION

        # 6. Confirm
        if any(p in text_lower for p in [
            "yes", "confirm", "confirmed", "that works", "see you then", "ok confirm", "sounds good",
            "yes please", "sure", "perfect", "suit me", "suits me", "agreed", "looking forward"
        ]):
            return TenantConfirmationResponseIntent.CONFIRM_VIEWING

        return TenantConfirmationResponseIntent.UNCLEAR

    def classify_agent_confirmation_intent(self, text: str, interactive_payload: Optional[Dict[str, Any]] = None) -> AgentConfirmationResponseIntent:
        """Classifies property agent confirmation response intent."""
        if interactive_payload:
            btn_id = str(interactive_payload.get("id") or interactive_payload.get("action") or "").lower()
            if "confirm" in btn_id:
                return AgentConfirmationResponseIntent.CONFIRM_VIEWING
            if "decline" in btn_id:
                return AgentConfirmationResponseIntent.DECLINE_VIEWING

        text_lower = text.lower().strip()

        # Property No Longer Available
        if any(p in text_lower for p in [
            "rented", "rented out", "already rented", "unit is rented", "deal closed", "off the market", "no longer available", "unit taken", "unit is taken"
        ]):
            return AgentConfirmationResponseIntent.PROPERTY_NO_LONGER_AVAILABLE

        # Slot No Longer Available / Decline
        if any(p in text_lower for p in [
            "slot taken", "slot no longer available", "no longer free", "already booked",
            "can't do that time", "busy at that time", "decline", "not available then"
        ]):
            return AgentConfirmationResponseIntent.SLOT_NO_LONGER_AVAILABLE

        if any(p in text_lower for p in ["no", "cannot make it", "can't do"]):
            return AgentConfirmationResponseIntent.DECLINE_VIEWING

        # Different time
        if any(p in text_lower for p in ["propose another", "can we do", "instead", "another time"]):
            return AgentConfirmationResponseIntent.REQUEST_DIFFERENT_TIME

        # Confirm
        if any(p in text_lower for p in [
            "confirm", "confirmed", "yes available", "ok noted", "see you then", "slot is available",
            "good to go", "yes", "noted with thanks", "agreed"
        ]):
            return AgentConfirmationResponseIntent.CONFIRM_VIEWING

        return AgentConfirmationResponseIntent.UNCLEAR

    def correlate_pending_viewing_for_tenant(
        self,
        lead_id: uuid.UUID,
        message_text: str,
        override_viewing_id: Optional[uuid.UUID] = None,
        interactive_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Viewing], bool, Optional[str]]:
        """
        Safely correlates tenant confirmation message to an active viewing.
        Resolves ambiguity across multiple active viewings.
        """
        if interactive_payload and interactive_payload.get("viewing_id"):
            try:
                v_id = uuid.UUID(str(interactive_payload["viewing_id"]))
                v = self.db.query(Viewing).filter(Viewing.id == v_id, Viewing.lead_id == lead_id).first()
                if v:
                    return v, False, None
            except Exception:
                pass

        if override_viewing_id:
            v = self.db.query(Viewing).filter(Viewing.id == override_viewing_id, Viewing.lead_id == lead_id).first()
            if v:
                return v, False, None

        # Find viewings awaiting confirmation or slot proposed
        candidate_viewings = (
            self.db.query(Viewing)
            .filter(
                Viewing.lead_id == lead_id,
                Viewing.status.in_([
                    ViewingStatus.SLOT_PROPOSED,
                    ViewingStatus.AWAITING_TENANT_CONFIRMATION,
                    ViewingStatus.AWAITING_AGENT_CONFIRMATION,
                ]),
            )
            .order_by(desc(Viewing.updated_at))
            .all()
        )

        if not candidate_viewings:
            return None, False, "No active viewing found awaiting confirmation."

        if len(candidate_viewings) == 1:
            return candidate_viewings[0], False, None

        # Check property reference in text
        text_lower = message_text.lower()
        matched = None
        for v in candidate_viewings:
            prop_name = (getattr(v.property, "canonical_name", None) or getattr(v.property, "building_name", None) or "").lower()
            if prop_name and prop_name in text_lower:
                matched = v
                break

        if matched:
            return matched, False, None

        # Ambiguous across multiple active viewings!
        prop_names = [f"'{getattr(v.property, 'canonical_name', 'Property')}'" for v in candidate_viewings if v.property]
        clarification = f"You have pending viewing confirmations for {' and '.join(prop_names)}. Which property are you confirming?"
        return None, True, clarification

    def correlate_pending_viewing_for_agent(
        self,
        agent_id: uuid.UUID,
        message_text: str,
        override_viewing_id: Optional[uuid.UUID] = None,
        interactive_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Viewing], bool, Optional[str]]:
        """
        Safely correlates agent confirmation message to an active viewing.
        """
        if interactive_payload and interactive_payload.get("viewing_id"):
            try:
                v_id = uuid.UUID(str(interactive_payload["viewing_id"]))
                v = self.db.query(Viewing).filter(Viewing.id == v_id, Viewing.property_agent_id == agent_id).first()
                if v:
                    return v, False, None
            except Exception:
                pass

        if override_viewing_id:
            v = self.db.query(Viewing).filter(Viewing.id == override_viewing_id, Viewing.property_agent_id == agent_id).first()
            if v:
                return v, False, None

        candidate_viewings = (
            self.db.query(Viewing)
            .filter(
                Viewing.property_agent_id == agent_id,
                Viewing.status.in_([
                    ViewingStatus.AWAITING_AGENT_CONFIRMATION,
                    ViewingStatus.SLOT_PROPOSED,
                    ViewingStatus.AWAITING_TENANT_CONFIRMATION,
                ]),
            )
            .order_by(desc(Viewing.updated_at))
            .all()
        )

        if not candidate_viewings:
            return None, False, "No active viewing found awaiting agent confirmation."

        if len(candidate_viewings) == 1:
            return candidate_viewings[0], False, None

        # Check listing ref in text
        text_upper = message_text.upper()
        for v in candidate_viewings:
            ref = (v.listing.listing_reference if v.listing else None) or (v.listing.source_listing_id if v.listing else None)
            if ref and ref.upper() in text_upper:
                return v, False, None

        # Ambiguous!
        return None, True, "Multiple active viewing confirmations exist for this agent and no listing reference was provided."

    def finalize_booking(
        self,
        viewing_id: uuid.UUID,
        actor_id: str = "system",
        reason: Optional[str] = None,
    ) -> ViewingFinalizeBookingResponse:
        """
        Atomically locks the candidate slot and finalizes booking:
        - Revalidates viewing, property, listing, proposed slot, and tenant eligibility.
        - Verifies required confirmation policy conditions:
          - tenant_confirmation_status == CONFIRMED (if required)
          - agent_confirmation_status == CONFIRMED (if required)
        - Locks the slot: marks candidate slot as BOOKED.
        - Demotes other candidate slots for this viewing.
        - Updates viewing scheduled timestamps.
        - Transitions viewing status to ViewingStatus.CONFIRMED.
        - Emits VIEWING_CONFIRMED event and audit log.
        - Dispatches booking confirmation WhatsApp notices to both parties.
        """
        validation = self.validate_for_confirmation(viewing_id)
        if not validation["valid"]:
            raise ValueError(f"Booking finalization blocked: {validation['reason']}")

        viewing: Viewing = validation["viewing"]
        slot: ViewingSlot = validation["proposed_slot"]
        lead: Lead = validation["lead"]
        prop: Property = validation["property"]
        listing: PropertyListing = validation["listing"]

        # Policy checks
        if self.policy.require_tenant_confirmation and viewing.tenant_confirmation_status != ViewingConfirmationStatus.CONFIRMED:
            raise ValueError(f"Tenant confirmation is required before final booking (current={viewing.tenant_confirmation_status.value}).")

        if self.policy.require_agent_confirmation and viewing.agent_confirmation_status != ViewingConfirmationStatus.CONFIRMED:
            raise ValueError(f"Agent confirmation is required before final booking (current={viewing.agent_confirmation_status.value}).")

        # 1. Lock slot transactionally: mark BOOKED
        slot.status = ViewingSlotStatus.BOOKED
        slot.is_mutual_match = True

        # Demote any other proposed / candidate slots for this viewing
        other_slots = (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing.id,
                ViewingSlot.id != slot.id,
                ViewingSlot.status.in_([ViewingSlotStatus.PROPOSED, ViewingSlotStatus.SELECTED]),
            )
            .all()
        )
        for os in other_slots:
            os.status = ViewingSlotStatus.AVAILABLE
            os.is_mutual_match = False

        # 2. Update Viewing schedule
        old_status = viewing.status.value
        viewing.scheduled_start_at = slot.start_at
        viewing.scheduled_end_at = slot.end_at or (slot.start_at + timedelta(minutes=viewing.duration_minutes or 30))
        viewing.timezone = slot.timezone

        booking_ref = self.get_booking_reference(viewing.id)

        # Transition status to CONFIRMED
        if ViewingStateMachine.can_transition(viewing.status, ViewingStatus.CONFIRMED):
            viewing.status = ViewingStatus.CONFIRMED
        else:
            raise ValueError(f"State machine rejected transition from {viewing.status} to CONFIRMED.")

        # 3. Log Audit & ViewingEvent
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.VIEWING_CONFIRMED,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR if actor_id == "operator" else ViewingActorType.SYSTEM,
            actor_id=actor_id,
            event_metadata={
                "action": "VIEWING_CONFIRMED",
                "booking_reference": booking_ref,
                "booked_slot_id": str(slot.id),
                "scheduled_start_at": slot.start_at.isoformat(),
                "scheduled_end_at": slot.end_at.isoformat() if slot.end_at else None,
                "reason": reason or "Both tenant and agent confirmations verified.",
            },
        )
        self.db.add(event)

        audit = AuditLog(
            action="VIEWING_CONFIRMED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={
                "booking_reference": booking_ref,
                "booked_slot_id": str(slot.id),
                "scheduled_start_at": slot.start_at.isoformat(),
                "scheduled_end_at": slot.end_at.isoformat() if slot.end_at else None,
                "tenant_confirmation": viewing.tenant_confirmation_status.value,
                "agent_confirmation": viewing.agent_confirmation_status.value,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(slot)
        self.db.refresh(viewing)

        # 4. Dispatch final booking confirmation notices to both parties
        slot_text = self.format_slot_display(slot, viewing)
        prop_title = getattr(prop, "canonical_name", None) or getattr(prop, "building_name", None) or "the property"
        prop_addr = getattr(prop, "address_line_1", None) or getattr(prop, "address_normalized", None) or "Address provided upon arrival"
        listing_ref = listing.listing_reference or listing.source_listing_id or "N/A"

        # Tenant confirmation acknowledgment
        try:
            profile = lead.assigned_whatsapp_profile or self.db.query(WhatsAppProfile).first()
            if profile and lead.phone_normalized:
                tenant_notice = (
                    f"🎉 Viewing Confirmed!\n\n"
                    f"Your viewing for {prop_title} has been booked:\n"
                    f"📅 {slot_text}\n"
                    f"📍 Location: {prop_addr}\n"
                    f"🔖 Booking Reference: {booking_ref}\n\n"
                    f"The property agent will meet you on site. If you have any questions, let us know!"
                )
                self.whatsapp_service.send_message(
                    profile_id=profile.id,
                    recipient=lead.phone_normalized,
                    content=tenant_notice,
                    idempotency_key=f"viewing:{viewing.id}:tenant-booking-ack:{slot.id}",
                )
        except Exception as e:
            logger.warning(f"Could not send tenant booking acknowledgment: {e}")

        # Agent confirmation acknowledgment
        try:
            agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == viewing.property_agent_id).first()
            profile = self.db.query(WhatsAppProfile).first()
            if profile and agent and agent.phone_normalized:
                agent_notice = (
                    f"✅ Viewing Confirmed!\n\n"
                    f"The viewing for {prop_title} (Listing Ref: {listing_ref}) is confirmed:\n"
                    f"📅 {slot_text}\n"
                    f"🔖 Booking Reference: {booking_ref}\n\n"
                    f"Please ensure access arrangements are prepared. Thank you!"
                )
                self.whatsapp_service.send_message(
                    profile_id=profile.id,
                    recipient=agent.phone_normalized,
                    content=agent_notice,
                    idempotency_key=f"viewing:{viewing.id}:agent-booking-ack:{slot.id}",
                )
        except Exception as e:
            logger.warning(f"Could not send agent booking acknowledgment: {e}")

        # 5. Automatically schedule viewing reminders (Module 5 Phase 6)
        try:
            from app.services.viewing_reminder_service import ViewingReminderService
            reminder_svc = ViewingReminderService(self.db, self.whatsapp_service)
            reminder_svc.schedule_reminders_for_viewing(
                viewing_id=viewing.id,
                booking_version=viewing.schedule_version,
                actor_id=actor_id,
            )
        except Exception as e:
            logger.warning(f"Could not automatically schedule reminders for viewing {viewing.id}: {e}")

        now_utc = datetime.now(dt_timezone.utc)
        return ViewingFinalizeBookingResponse(
            viewing_id=viewing.id,
            booking_reference=booking_ref,
            status=viewing.status.value,
            booked_slot_id=slot.id,
            scheduled_start_at=viewing.scheduled_start_at,
            scheduled_end_at=viewing.scheduled_end_at,
            timezone=viewing.timezone or ViewingConfig.DEFAULT_TIMEZONE,
            location_text=prop_addr,
            meeting_url=viewing.meeting_url,
            tenant_notified=True,
            agent_notified=True,
            confirmed_at=now_utc,
        )

    async def process_inbound_tenant_confirmation(
        self,
        message_id: Optional[uuid.UUID] = None,
        raw_text: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
        override_viewing_id: Optional[uuid.UUID] = None,
        interactive_payload: Optional[Dict[str, Any]] = None,
        actor_id: str = "tenant",
    ) -> TenantConfirmationUnderstandingResult:
        """
        Processes inbound tenant confirmation reply.
        - Correlates viewing safely.
        - Classifies confirmation intent.
        - Updates tenant_confirmation_status.
        - Automatically finalizes booking if agent is already confirmed (or not required).
        """
        text_content = ""
        msg: Optional[WhatsAppMessage] = None
        if message_id:
            msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
            if msg:
                text_content = msg.content or ""
                if msg.raw_payload and isinstance(msg.raw_payload, dict):
                    interactive = msg.raw_payload.get("interactive") or {}
                    if interactive:
                        interactive_payload = interactive.get("button_reply") or interactive.get("list_reply")
        if raw_text:
            text_content = raw_text

        if not lead_id and msg:
            lead = self.db.query(Lead).filter(Lead.phone_normalized == msg.sender).first()
            if lead:
                lead_id = lead.id

        if not lead_id:
            raise ValueError("Cannot resolve tenant lead for confirmation message.")

        viewing, needs_clarification, clar_q = self.correlate_pending_viewing_for_tenant(
            lead_id=lead_id,
            message_text=text_content,
            override_viewing_id=override_viewing_id,
            interactive_payload=interactive_payload,
        )

        if needs_clarification or not viewing:
            return TenantConfirmationUnderstandingResult(
                intent=TenantConfirmationResponseIntent.UNCLEAR,
                correlated_viewing_id=None,
                confidence=0.5,
                needs_clarification=True,
                clarification_question=clar_q or "Which property viewing are you confirming?",
                raw_response=text_content,
                metadata={"status": "AMBIGUOUS_CORRELATION"},
            )

        intent = self.classify_tenant_intent(text_content, interactive_payload)

        # 1. Cancel
        if intent == TenantConfirmationResponseIntent.CANCEL_VIEWING:
            ViewingService.cancel_viewing(
                db=self.db,
                viewing_id=viewing.id,
                reason="Tenant cancelled viewing during confirmation flow.",
                cancelled_by="tenant",
            )
            return TenantConfirmationUnderstandingResult(
                intent=intent,
                correlated_viewing_id=viewing.id,
                confidence=0.98,
                needs_clarification=False,
                raw_response=text_content,
                metadata={"status": "VIEWING_CANCELLED"},
            )

        # 2. Decline or Request Different Time
        if intent in [TenantConfirmationResponseIntent.DECLINE_VIEWING, TenantConfirmationResponseIntent.REQUEST_DIFFERENT_TIME]:
            viewing.tenant_confirmation_status = ViewingConfirmationStatus.DECLINED
            # Release proposed slot
            slot = self.get_proposed_slot(viewing.id)
            if slot:
                slot.status = ViewingSlotStatus.AVAILABLE
                slot.is_mutual_match = False

            # Return viewing to scheduling state
            if viewing.status in [ViewingStatus.SLOT_PROPOSED, ViewingStatus.AWAITING_TENANT_CONFIRMATION]:
                viewing.status = ViewingStatus.AWAITING_TENANT_AVAILABILITY

            # Audit event
            event = ViewingEvent(
                viewing_id=viewing.id,
                event_type=ViewingEventType.TENANT_DECLINED,
                old_status=viewing.status.value,
                new_status=viewing.status.value,
                actor_type=ViewingActorType.TENANT,
                actor_id=actor_id,
                event_metadata={"reason": "Tenant declined proposed slot.", "raw_response": text_content},
            )
            self.db.add(event)
            self.db.commit()

            return TenantConfirmationUnderstandingResult(
                intent=intent,
                correlated_viewing_id=viewing.id,
                confidence=0.95,
                needs_clarification=False,
                clarification_question="What times would work better for your viewing?",
                raw_response=text_content,
                metadata={"status": "TENANT_DECLINED_RETURNED_TO_SCHEDULING"},
            )

        # 3. Question
        if intent == TenantConfirmationResponseIntent.ASK_VIEWING_QUESTION:
            prop = viewing.property
            prop_title = getattr(prop, "canonical_name", None) or getattr(prop, "building_name", None) or ""
            prop_addr = getattr(prop, "address_line_1", None) or ""
            ans = f"The viewing is for {prop_title} located at {prop_addr}."
            return TenantConfirmationUnderstandingResult(
                intent=intent,
                correlated_viewing_id=viewing.id,
                confidence=0.90,
                needs_clarification=False,
                raw_response=text_content,
                metadata={"answer": ans},
            )

        # 4. Confirm
        if intent == TenantConfirmationResponseIntent.CONFIRM_VIEWING:
            viewing.tenant_confirmation_status = ViewingConfirmationStatus.CONFIRMED

            event = ViewingEvent(
                viewing_id=viewing.id,
                event_type=ViewingEventType.TENANT_CONFIRMED,
                old_status=viewing.status.value,
                new_status=viewing.status.value,
                actor_type=ViewingActorType.TENANT,
                actor_id=actor_id,
                event_metadata={"raw_response": text_content},
            )
            self.db.add(event)
            self.db.commit()
            self.db.refresh(viewing)

            # Check if agent confirmation is already confirmed (or not required)
            agent_ready = (
                not self.policy.require_agent_confirmation
                or viewing.agent_confirmation_status == ViewingConfirmationStatus.CONFIRMED
            )

            if agent_ready:
                # Both confirmed -> Finalize Booking!
                try:
                    self.finalize_booking(
                        viewing_id=viewing.id,
                        actor_id="system",
                        reason="Tenant confirmed and agent confirmation already verified.",
                    )
                    return TenantConfirmationUnderstandingResult(
                        intent=intent,
                        correlated_viewing_id=viewing.id,
                        confidence=0.98,
                        needs_clarification=False,
                        raw_response=text_content,
                        metadata={"status": "BOOKING_CONFIRMED"},
                    )
                except Exception as e:
                    logger.error(f"Error finalizing booking after tenant confirm: {e}")

            # Agent not ready yet -> transition viewing to AWAITING_AGENT_CONFIRMATION
            if viewing.status != ViewingStatus.CONFIRMED:
                if ViewingStateMachine.can_transition(viewing.status, ViewingStatus.AWAITING_AGENT_CONFIRMATION):
                    viewing.status = ViewingStatus.AWAITING_AGENT_CONFIRMATION
                    self.db.commit()

            return TenantConfirmationUnderstandingResult(
                intent=intent,
                correlated_viewing_id=viewing.id,
                confidence=0.95,
                needs_clarification=False,
                raw_response=text_content,
                metadata={"status": "TENANT_CONFIRMED_AWAITING_AGENT"},
            )

        return TenantConfirmationUnderstandingResult(
            intent=intent,
            correlated_viewing_id=viewing.id,
            confidence=0.6,
            needs_clarification=True,
            clarification_question="Please reply 'CONFIRM' if this time works, or let us know if you need to choose another slot.",
            raw_response=text_content,
            metadata={},
        )

    def classify_tenant_intent(self, text: str, interactive_payload: Optional[Dict[str, Any]] = None) -> TenantConfirmationResponseIntent:
        """Alias for classify_tenant_confirmation_intent."""
        return self.classify_tenant_confirmation_intent(text, interactive_payload)

    async def process_inbound_agent_confirmation(
        self,
        message_id: Optional[uuid.UUID] = None,
        raw_text: Optional[str] = None,
        agent_id: Optional[uuid.UUID] = None,
        override_viewing_id: Optional[uuid.UUID] = None,
        interactive_payload: Optional[Dict[str, Any]] = None,
        actor_id: str = "property_agent",
    ) -> AgentConfirmationUnderstandingResult:
        """
        Processes inbound property agent confirmation reply.
        - Correlates viewing safely.
        - Classifies agent intent.
        - Handles property/slot unavailability.
        - Updates agent_confirmation_status.
        - Finalizes booking if tenant is also confirmed.
        """
        text_content = ""
        msg: Optional[WhatsAppMessage] = None
        if message_id:
            msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
            if msg:
                text_content = msg.content or ""
                if msg.raw_payload and isinstance(msg.raw_payload, dict):
                    interactive = msg.raw_payload.get("interactive") or {}
                    if interactive:
                        interactive_payload = interactive.get("button_reply") or interactive.get("list_reply")
        if raw_text:
            text_content = raw_text

        if not agent_id and msg:
            agent = (
                self.db.query(PropertyAgent)
                .filter(or_(PropertyAgent.phone_normalized == msg.sender, PropertyAgent.phone == msg.sender))
                .first()
            )
            if agent:
                agent_id = agent.id

        if not agent_id:
            raise ValueError("Cannot resolve property agent for confirmation message.")

        viewing, needs_clarification, clar_q = self.correlate_pending_viewing_for_agent(
            agent_id=agent_id,
            message_text=text_content,
            override_viewing_id=override_viewing_id,
            interactive_payload=interactive_payload,
        )

        if needs_clarification or not viewing:
            return AgentConfirmationUnderstandingResult(
                intent=AgentConfirmationResponseIntent.UNCLEAR,
                correlated_viewing_id=None,
                confidence=0.5,
                needs_clarification=True,
                clarification_question=clar_q or "Which viewing appointment are you confirming?",
                raw_response=text_content,
                metadata={"status": "AMBIGUOUS_CORRELATION"},
            )

        intent = self.classify_agent_confirmation_intent(text_content, interactive_payload)

        # 1. Property No Longer Available
        if intent == AgentConfirmationResponseIntent.PROPERTY_NO_LONGER_AVAILABLE:
            if viewing.listing:
                viewing.listing.availability_status = ListingAvailabilityStatus.UNAVAILABLE
            viewing.status = ViewingStatus.CANCELLED
            viewing.cancellation_reason = "Property agent reported property no longer available."
            viewing.cancelled_by = "property_agent"
            viewing.agent_confirmation_status = ViewingConfirmationStatus.DECLINED
            self.db.commit()

            return AgentConfirmationUnderstandingResult(
                intent=intent,
                correlated_viewing_id=viewing.id,
                confidence=0.98,
                needs_clarification=False,
                raw_response=text_content,
                metadata={"status": "PROPERTY_UNAVAILABLE_VIEWING_CANCELLED"},
            )

        # 2. Decline or Slot No Longer Available
        if intent in [
            AgentConfirmationResponseIntent.DECLINE_VIEWING,
            AgentConfirmationResponseIntent.SLOT_NO_LONGER_AVAILABLE,
            AgentConfirmationResponseIntent.REQUEST_DIFFERENT_TIME,
        ]:
            viewing.agent_confirmation_status = ViewingConfirmationStatus.DECLINED
            slot = self.get_proposed_slot(viewing.id)
            if slot:
                slot.status = ViewingSlotStatus.REJECTED
                slot.is_mutual_match = False

            # Viewing returns to slot selection flow
            if viewing.status in [ViewingStatus.AWAITING_AGENT_CONFIRMATION, ViewingStatus.SLOT_PROPOSED]:
                viewing.status = ViewingStatus.SLOTS_AVAILABLE

            event = ViewingEvent(
                viewing_id=viewing.id,
                event_type=ViewingEventType.AGENT_DECLINED,
                old_status=viewing.status.value,
                new_status=viewing.status.value,
                actor_type=ViewingActorType.PROPERTY_AGENT,
                actor_id=actor_id,
                event_metadata={"reason": "Agent declined slot.", "raw_response": text_content},
            )
            self.db.add(event)
            self.db.commit()

            return AgentConfirmationUnderstandingResult(
                intent=intent,
                correlated_viewing_id=viewing.id,
                confidence=0.95,
                needs_clarification=False,
                raw_response=text_content,
                metadata={"status": "AGENT_DECLINED_RETURNED_TO_SLOTS"},
            )

        # 3. Confirm
        if intent == AgentConfirmationResponseIntent.CONFIRM_VIEWING:
            viewing.agent_confirmation_status = ViewingConfirmationStatus.CONFIRMED

            event = ViewingEvent(
                viewing_id=viewing.id,
                event_type=ViewingEventType.AGENT_CONFIRMED,
                old_status=viewing.status.value,
                new_status=viewing.status.value,
                actor_type=ViewingActorType.PROPERTY_AGENT,
                actor_id=actor_id,
                event_metadata={"raw_response": text_content},
            )
            self.db.add(event)
            self.db.commit()
            self.db.refresh(viewing)

            # Check if tenant is ready
            tenant_ready = (
                not self.policy.require_tenant_confirmation
                or viewing.tenant_confirmation_status == ViewingConfirmationStatus.CONFIRMED
            )

            if tenant_ready:
                # Both confirmed -> Finalize Booking!
                try:
                    self.finalize_booking(
                        viewing_id=viewing.id,
                        actor_id="system",
                        reason="Agent confirmed and tenant confirmation verified.",
                    )
                    return AgentConfirmationUnderstandingResult(
                        intent=intent,
                        correlated_viewing_id=viewing.id,
                        confidence=0.98,
                        needs_clarification=False,
                        raw_response=text_content,
                        metadata={"status": "BOOKING_CONFIRMED"},
                    )
                except Exception as e:
                    logger.error(f"Error finalizing booking after agent confirm: {e}")

            return AgentConfirmationUnderstandingResult(
                intent=intent,
                correlated_viewing_id=viewing.id,
                confidence=0.95,
                needs_clarification=False,
                raw_response=text_content,
                metadata={"status": "AGENT_CONFIRMED_AWAITING_TENANT"},
            )

        return AgentConfirmationUnderstandingResult(
            intent=intent,
            correlated_viewing_id=viewing.id,
            confidence=0.6,
            needs_clarification=True,
            clarification_question="Please reply 'CONFIRM' if this viewing slot is available, or 'DECLINE' if unavailable.",
            raw_response=text_content,
            metadata={},
        )

    def manual_confirm(
        self,
        viewing_id: uuid.UUID,
        party: ConfirmationParty,
        actor_id: str = "operator",
        reason: str = "Operator recorded manual confirmation",
        notes: Optional[str] = None,
    ) -> ViewingConfirmationStatusOverview:
        """
        Records manual confirmation on behalf of tenant or agent (e.g. phone call).
        """
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        old_status = viewing.status.value
        if party == ConfirmationParty.TENANT:
            viewing.tenant_confirmation_status = ViewingConfirmationStatus.CONFIRMED
            event_type = ViewingEventType.TENANT_CONFIRMED
            if viewing.agent_confirmation_status != ViewingConfirmationStatus.CONFIRMED:
                viewing.status = ViewingStatus.AWAITING_AGENT_CONFIRMATION
        else:
            viewing.agent_confirmation_status = ViewingConfirmationStatus.CONFIRMED
            event_type = ViewingEventType.AGENT_CONFIRMED
            if viewing.tenant_confirmation_status != ViewingConfirmationStatus.CONFIRMED:
                viewing.status = ViewingStatus.AWAITING_TENANT_CONFIRMATION

        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=event_type,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR,
            actor_id=actor_id,
            event_metadata={"action": f"MANUAL_{party.value}_CONFIRMED", "reason": reason, "notes": notes},
        )
        self.db.add(event)

        audit = AuditLog(
            action=f"MANUAL_{party.value}_CONFIRMATION",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={"party": party.value, "reason": reason, "notes": notes},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(viewing)

        # Check if both now confirmed and can finalize
        both_confirmed = (
            viewing.tenant_confirmation_status == ViewingConfirmationStatus.CONFIRMED
            and viewing.agent_confirmation_status == ViewingConfirmationStatus.CONFIRMED
        )
        if both_confirmed and getattr(self.policy, "auto_confirm_if_both_preconfirmed", False):
            try:
                self.finalize_booking(viewing_id=viewing.id, actor_id=actor_id, reason=reason)
            except Exception as e:
                logger.warning(f"Could not auto-finalize on manual confirm: {e}")

        return self.get_confirmation_status_overview(viewing.id)

    def manual_decline(
        self,
        viewing_id: uuid.UUID,
        party: ConfirmationParty,
        actor_id: str = "operator",
        reason: str = "Operator recorded decline",
    ) -> ViewingConfirmationStatusOverview:
        """
        Records manual decline on behalf of tenant or agent.
        """
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        old_status = viewing.status.value
        slot = self.get_proposed_slot(viewing.id)

        if party == ConfirmationParty.TENANT:
            viewing.tenant_confirmation_status = ViewingConfirmationStatus.DECLINED
            event_type = ViewingEventType.TENANT_DECLINED
            if slot:
                slot.status = ViewingSlotStatus.REJECTED
                slot.is_mutual_match = False
            viewing.status = ViewingStatus.SLOTS_AVAILABLE
        else:
            viewing.agent_confirmation_status = ViewingConfirmationStatus.DECLINED
            event_type = ViewingEventType.AGENT_DECLINED
            if slot:
                slot.status = ViewingSlotStatus.REJECTED
                slot.is_mutual_match = False
            viewing.status = ViewingStatus.SLOTS_AVAILABLE

        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=event_type,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR,
            actor_id=actor_id,
            event_metadata={"action": f"MANUAL_{party.value}_DECLINE", "reason": reason},
        )
        self.db.add(event)

        audit = AuditLog(
            action=f"MANUAL_{party.value}_DECLINE",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={"party": party.value, "reason": reason},
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(viewing)
        return self.get_confirmation_status_overview(viewing.id)

    def get_confirmation_status_overview(self, viewing_id: uuid.UUID) -> ViewingConfirmationStatusOverview:
        """Loads comprehensive confirmation status overview for viewing detail UI."""
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        proposed_slot = self.get_proposed_slot(viewing.id)
        booked_slot = self.get_booked_slot(viewing.id)

        both_confirmed = (
            viewing.tenant_confirmation_status == ViewingConfirmationStatus.CONFIRMED
            and viewing.agent_confirmation_status == ViewingConfirmationStatus.CONFIRMED
        )
        can_finalize = (
            both_confirmed
            and viewing.status != ViewingStatus.CONFIRMED
            and proposed_slot is not None
        )

        prop_addr = getattr(viewing.property, "address_line_1", None) or getattr(viewing.property, "address_normalized", None)

        return ViewingConfirmationStatusOverview(
            viewing_id=viewing.id,
            booking_reference=self.get_booking_reference(viewing.id),
            viewing_status=viewing.status.value,
            tenant_confirmation_status=viewing.tenant_confirmation_status,
            agent_confirmation_status=viewing.agent_confirmation_status,
            proposed_slot=ViewingSlotResponse.from_orm(proposed_slot) if proposed_slot else None,
            booked_slot=ViewingSlotResponse.from_orm(booked_slot) if booked_slot else None,
            scheduled_start_at=viewing.scheduled_start_at,
            scheduled_end_at=viewing.scheduled_end_at,
            timezone=viewing.timezone or ViewingConfig.DEFAULT_TIMEZONE,
            location_type=viewing.location_type.value if hasattr(viewing.location_type, "value") else "IN_PERSON",
            location_text=prop_addr,
            meeting_url=viewing.meeting_url,
            policy_summary={
                "require_tenant_confirmation": self.policy.require_tenant_confirmation,
                "require_agent_confirmation": self.policy.require_agent_confirmation,
                "confirmation_timeout_minutes": self.policy.confirmation_timeout_minutes,
                "version": self.policy.version,
            },
            can_finalize=can_finalize,
            is_confirmed=(viewing.status == ViewingStatus.CONFIRMED),
        )
