"""
Tenant Viewing Availability Service - Module 5 Phase 4
Prepares tenant-facing viewing availability inquiries or slot choices,
sends them via WhatsApp, enforces idempotency, respects human takeover,
and transitions viewing lifecycle safely.
"""
import uuid
import logging
from datetime import datetime, timezone as dt_timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.lead import Lead
from app.models.property_match import PropertyMatch
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.whatsapp import WhatsAppProfile
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingActorType,
    PropertyListingStatus,
    ListingAvailabilityStatus,
    PropertyStatus,
    ContactEligibility,
    LeadStatus,
)
from app.schemas.viewing import ViewingSlotResponse
from app.schemas.viewing_availability import (
    TenantViewingAvailabilityRequestCreate,
    TenantViewingAvailabilityRequestResponse,
)
from app.services.whatsapp_service import WhatsAppService
from app.services.viewing_slot_matching_service import ViewingSlotMatchingService
from app.services.viewing_state_machine import ViewingStateMachine

logger = logging.getLogger(__name__)


class TenantViewingAvailabilityService:
    """
    Coordinates tenant viewing availability inquiries and slot offers.
    Responsibilities:
    - Validate entry condition: viewing active, slots available, listing active, tenant eligible.
    - Check Human Takeover status: abort auto-send if operator has taken over.
    - Formats clear slot options (Strategy A: Offer agent slots directly; Strategy B: General ask).
    - Dispatches WhatsApp message using idempotency key: viewing:{viewing_id}:tenant-availability-request:{version}.
    - Transitions viewing state to AWAITING_TENANT_AVAILABILITY.
    - Emits audit log and ViewingEvent.
    """

    def __init__(self, db: Session, whatsapp_service: Optional[WhatsAppService] = None):
        self.db = db
        self.whatsapp_service = whatsapp_service or WhatsAppService(db)
        self.slot_matching_service = ViewingSlotMatchingService(db)

    def validate_entry_conditions(self, viewing_id: uuid.UUID) -> Dict[str, Any]:
        """
        Validates all prerequisites before asking tenant for availability.
        - Viewing exists and is active (not CANCELLED, COMPLETED, NO_SHOW, REJECTED)
        - Viewing status is SLOTS_AVAILABLE or AWAITING_TENANT_AVAILABILITY
        - Property & listing remain active and available
        - Lead is eligible and not opted out
        - At least one active, non-expired property-agent slot exists (if Strategy A)
        """
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
        if not listing or listing.listing_status in [PropertyListingStatus.INACTIVE, PropertyListingStatus.REMOVED, PropertyListingStatus.EXPIRED] or listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE:
            return {"valid": False, "reason": "Listing is no longer available.", "viewing": viewing}

        # Check Tenant / Lead eligibility
        lead = self.db.query(Lead).filter(Lead.id == viewing.lead_id).first()
        if not lead or lead.contact_eligibility != ContactEligibility.ELIGIBLE:
            return {"valid": False, "reason": "Lead is ineligible or has opted out of contact.", "viewing": viewing}

        # Check human takeover
        req = lead.tenant_requirement
        is_human_takeover = getattr(lead, "human_takeover", False)
        if req:
            if getattr(req, "ai_paused", False) or getattr(req, "qualification_mode", None) == "HUMAN_REVIEW":
                is_human_takeover = True

        if is_human_takeover:
            return {
                "valid": False,
                "reason": "Tenant conversation is under HUMAN_TAKEOVER. Automation paused.",
                "viewing": viewing,
                "human_takeover": True,
            }

        # Check agent slots
        active_agent_slots = self.slot_matching_service.get_active_agent_slots(viewing.id)
        if not active_agent_slots and viewing.status == ViewingStatus.SLOTS_AVAILABLE:
            return {
                "valid": False,
                "reason": "No active, unexpired property-agent slots available for viewing.",
                "viewing": viewing,
            }

        return {
            "valid": True,
            "viewing": viewing,
            "lead": lead,
            "listing": listing,
            "property": prop,
            "agent_slots": active_agent_slots,
        }

    def compose_tenant_slot_message(
        self,
        viewing: Viewing,
        agent_slots: List[ViewingSlot],
        strategy: str = "OFFER_AGENT_SLOTS",
        custom_message: Optional[str] = None,
    ) -> str:
        """
        Builds friendly, concise WhatsApp message for the tenant.
        Strategy A: Offer agent slots directly with numbered options.
        Strategy B: General ask.
        """
        prop_title = (
            getattr(viewing.property, "canonical_name", None)
            or getattr(viewing.property, "building_name", None)
            or "the requested property"
        )

        if custom_message:
            return custom_message

        if strategy == "OFFER_AGENT_SLOTS" and agent_slots:
            slot_lines = []
            for idx, slot in enumerate(agent_slots[:5], start=1):
                s_dt = ViewingSlotMatchingService.to_display_tz(
                    ViewingSlotMatchingService.to_utc(slot.start_at, slot.timezone),
                    viewing.timezone or "Asia/Singapore",
                )
                slot_lines.append(f"{idx}. {s_dt.strftime('%A, %d %b at %I:%M %p')}")

            body = (
                f"Great news! The property agent for {prop_title} has provided available viewing times:\n\n"
                + "\n".join(slot_lines)
                + "\n\nWhich time works best for you? You can reply with the number or your preferred time."
            )
            return body
        else:
            return (
                f"We are coordinating your viewing for {prop_title}. "
                f"What times are convenient for you this week or upcoming weekend?"
            )

    def request_tenant_availability(
        self,
        viewing_id: uuid.UUID,
        payload: Optional[TenantViewingAvailabilityRequestCreate] = None,
        actor_id: str = "operator",
    ) -> TenantViewingAvailabilityRequestResponse:
        """
        Orchestrates sending viewing availability options to tenant.
        1. Validates entry condition.
        2. Generates idempotency key: viewing:{viewing_id}:tenant-availability-request:{version}.
        3. Composes message text & interactive slot data.
        4. Sends WhatsApp message.
        5. Updates viewing status to AWAITING_TENANT_AVAILABILITY.
        6. Logs audit event and ViewingEvent.
        """
        validation = self.validate_entry_conditions(viewing_id)
        if not validation["valid"]:
            raise ValueError(f"Viewing availability request rejected: {validation['reason']}")

        viewing: Viewing = validation["viewing"]
        lead: Lead = validation["lead"]
        agent_slots: List[ViewingSlot] = validation.get("agent_slots", [])

        strategy = payload.strategy if payload and payload.strategy else "OFFER_AGENT_SLOTS"
        custom_msg = payload.custom_message if payload else None

        # Build idempotency key
        req_version = viewing.reschedule_count + 1
        idempotency_key = f"viewing:{viewing.id}:tenant-availability-request:{req_version}"

        # Compose message
        msg_text = self.compose_tenant_slot_message(
            viewing=viewing,
            agent_slots=agent_slots,
            strategy=strategy,
            custom_message=custom_msg,
        )

        # Dispatch via WhatsAppService
        provider_msg_id = None
        message_sent = False
        try:
            profile = lead.assigned_whatsapp_profile or self.db.query(WhatsAppProfile).first()
            if profile and lead.phone_normalized:
                wa_msg = self.whatsapp_service.send_message(
                    profile_id=profile.id,
                    recipient=lead.phone_normalized,
                    content=msg_text,
                    idempotency_key=idempotency_key,
                )
                provider_msg_id = wa_msg.provider_message_id
                message_sent = True
        except Exception as e:
            logger.error(f"Failed to dispatch tenant availability message: {e}")
            raise RuntimeError(f"WhatsApp dispatch failed: {str(e)}")

        # Transition viewing state if currently SLOTS_AVAILABLE
        old_status = viewing.status.value
        if viewing.status == ViewingStatus.SLOTS_AVAILABLE:
            if ViewingStateMachine.can_transition(viewing.status, ViewingStatus.AWAITING_TENANT_AVAILABILITY):
                viewing.status = ViewingStatus.AWAITING_TENANT_AVAILABILITY

        # Add ViewingEvent
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.STATUS_CHANGED,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR if actor_id == "operator" else ViewingActorType.SYSTEM,
            actor_id=actor_id,
            event_metadata={
                "action": "TENANT_AVAILABILITY_REQUESTED",
                "strategy": strategy,
                "slots_offered_count": len(agent_slots),
                "idempotency_key": idempotency_key,
                "provider_message_id": provider_msg_id,
            },
        )
        self.db.add(event)

        # Audit log
        audit = AuditLog(
            action="TENANT_AVAILABILITY_REQUESTED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={
                "lead_id": str(lead.id),
                "strategy": strategy,
                "offered_slots": [str(s.id) for s in agent_slots],
                "idempotency_key": idempotency_key,
                "provider_message_id": provider_msg_id,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(viewing)

        offered_slot_responses = [
            ViewingSlotResponse.from_orm(s) for s in agent_slots
        ]

        return TenantViewingAvailabilityRequestResponse(
            viewing_id=viewing.id,
            lead_id=lead.id,
            strategy=strategy,
            message_sent=message_sent,
            provider_message_id=provider_msg_id,
            offered_slots=offered_slot_responses,
            sent_at=datetime.now(dt_timezone.utc),
        )
