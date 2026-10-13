"""
Viewing Operation Understanding Service - Module 5 Phase 6
Analyzes inbound WhatsApp messages from Tenants and Property Agents regarding
CONFIRMED or RESCHEDULE_REQUESTED viewings (reminders replies, reschedules, cancellations).
Safely correlates multi-viewing contexts and prevents arbitrary AI state mutations.
"""
import uuid
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.viewing import Viewing, ViewingSlot
from app.models.lead import Lead
from app.models.property import Property
from app.models.property_agent import PropertyAgent
from app.models.message import WhatsAppMessage
from app.models.whatsapp import WhatsAppProfile
from app.models.enums import (
    ViewingStatus,
    ViewingOperationIntent,
)
from app.ai.orchestrator import AIOrchestrator
from app.services.viewing_reschedule_service import ViewingRescheduleService
from app.services.viewing_cancellation_service import ViewingCancellationService
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class ViewingOperationUnderstandingService:
    """
    Understands tenant and agent replies concerning confirmed viewings.
    Deterministic rule-based classification with AIOrchestrator fallback.
    """

    RESCHEDULE_PATTERNS = [
        r"\b(?:reschedule|change\s+time|move\s+to|postpone|different\s+time|another\s+day|can\s+we\s+do|no\s+longer\s+works)\b",
        r"\b(?:switch|shift|push\s+back|delay)\b",
    ]

    CANCEL_PATTERNS = [
        r"\b(?:cancel|cancelling|cancelled|can't\s+make\s+it|cannot\s+make\s+it|won't\s+be\s+able\s+to\s+come|drop\s+it|nevermind)\b",
    ]

    CONFIRM_PATTERNS = [
        r"^(?:yes|yep|yeah|confirm|confirmed|ok|okay|sure|see\s+you\s+then|will\s+be\s+there)\b",
    ]

    def __init__(
        self,
        db: Session,
        orchestrator: Optional[AIOrchestrator] = None,
        wa_service: Optional[WhatsAppService] = None,
    ):
        self.db = db
        self.orchestrator = orchestrator or AIOrchestrator()
        self.whatsapp_service = wa_service or WhatsAppService(db)
        self.reschedule_service = ViewingRescheduleService(db, self.whatsapp_service)
        self.cancellation_service = ViewingCancellationService(db, self.whatsapp_service)

    def correlate_viewing_for_tenant(
        self,
        lead_id: uuid.UUID,
        message_text: str,
        override_viewing_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Optional[Viewing], bool, Optional[str]]:
        """
        Correlates tenant message to an active/confirmed viewing.
        Handles single viewing, property/date keywords, and ambiguous multi-viewings safely.
        """
        if override_viewing_id:
            v = self.db.query(Viewing).filter(Viewing.id == override_viewing_id, Viewing.lead_id == lead_id).first()
            if v:
                return v, False, None

        # Look for CONFIRMED or RESCHEDULE_REQUESTED viewings
        active_viewings = (
            self.db.query(Viewing)
            .filter(
                Viewing.lead_id == lead_id,
                Viewing.status.in_([
                    ViewingStatus.CONFIRMED,
                    ViewingStatus.RESCHEDULE_REQUESTED,
                ]),
            )
            .order_by(desc(Viewing.updated_at))
            .all()
        )

        if not active_viewings:
            return None, False, None

        if len(active_viewings) == 1:
            return active_viewings[0], False, None

        # Multiple confirmed viewings: inspect message text for property name or date clues
        text_lower = message_text.lower()
        matched = []
        for v in active_viewings:
            prop = v.property or self.db.query(Property).filter(Property.id == v.property_id).first()
            prop_name = (getattr(prop, "canonical_name", None) or getattr(prop, "building_name", None) or "").lower()
            prop_addr = (getattr(prop, "address_line_1", None) or "").lower()

            day_match = False
            if v.scheduled_start_at:
                day_name = v.scheduled_start_at.strftime("%A").lower()  # e.g. "saturday"
                short_day = v.scheduled_start_at.strftime("%a").lower()  # e.g. "sat"
                date_num = str(v.scheduled_start_at.day)
                if day_name in text_lower or short_day in text_lower or date_num in text_lower:
                    day_match = True

            name_words = [w for w in prop_name.split() if len(w) >= 3 and w not in ["the", "residence", "condo", "apartment", "building"]]
            name_match = (prop_name and prop_name in text_lower) or any(w in text_lower for w in name_words)
            addr_words = [w for w in prop_addr.split() if len(w) >= 3 and not w.isdigit()]
            addr_match = (prop_addr and prop_addr in text_lower) or any(w in text_lower for w in addr_words)

            if name_match or addr_match or day_match:
                matched.append(v)

        if len(matched) == 1:
            return matched[0], False, None

        # Ambiguous multi-viewings: return needs_clarification
        return (
            None,
            True,
            "You have multiple upcoming viewings. Could you please specify which property or date you are referring to?",
        )

    def correlate_viewing_for_agent(
        self,
        agent_id: uuid.UUID,
        message_text: str,
        override_viewing_id: Optional[uuid.UUID] = None,
    ) -> Tuple[Optional[Viewing], bool, Optional[str]]:
        """
        Correlates agent message to an active/confirmed viewing.
        """
        if override_viewing_id:
            v = self.db.query(Viewing).filter(Viewing.id == override_viewing_id, Viewing.property_agent_id == agent_id).first()
            if v:
                return v, False, None

        active_viewings = (
            self.db.query(Viewing)
            .filter(
                Viewing.property_agent_id == agent_id,
                Viewing.status.in_([
                    ViewingStatus.CONFIRMED,
                    ViewingStatus.RESCHEDULE_REQUESTED,
                ]),
            )
            .order_by(desc(Viewing.updated_at))
            .all()
        )

        if not active_viewings:
            return None, False, None

        if len(active_viewings) == 1:
            return active_viewings[0], False, None

        # Match by listing reference or property name
        text_lower = message_text.lower()
        matched = []
        for v in active_viewings:
            ref = (getattr(v.listing, "listing_reference", None) or getattr(v.listing, "source_listing_id", None) or "").lower()
            prop_name = (getattr(v.property, "canonical_name", None) or "").lower()
            if (ref and ref in text_lower) or (prop_name and prop_name in text_lower):
                matched.append(v)

        if len(matched) == 1:
            return matched[0], False, None

        return (
            None,
            True,
            "You have multiple scheduled viewings. Please mention the property or listing reference you are referring to.",
        )

    def classify_intent(self, message_text: str) -> ViewingOperationIntent:
        """
        Deterministic regex classification with safe fallback.
        """
        text_clean = message_text.strip().lower()

        # Check cancellations first
        for pat in self.CANCEL_PATTERNS:
            if re.search(pat, text_clean):
                return ViewingOperationIntent.CANCEL_VIEWING

        # Check reschedule
        for pat in self.RESCHEDULE_PATTERNS:
            if re.search(pat, text_clean):
                return ViewingOperationIntent.REQUEST_RESCHEDULE

        # Check confirmation
        for pat in self.CONFIRM_PATTERNS:
            if re.search(pat, text_clean):
                return ViewingOperationIntent.CONFIRM_CURRENT_VIEWING

        return ViewingOperationIntent.UNCLEAR

    async def process_inbound_tenant_operation(
        self,
        message_id: uuid.UUID,
        lead_id: uuid.UUID,
        actor_id: str = "tenant",
        override_viewing_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Processes inbound message from tenant concerning confirmed/active viewings.
        """
        msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
        content = (msg.content or "").strip() if msg else ""

        viewing, needs_clarification, question = self.correlate_viewing_for_tenant(
            lead_id=lead_id,
            message_text=content,
            override_viewing_id=override_viewing_id,
        )

        if needs_clarification and question:
            # Send clarification message back to tenant
            lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
            if lead and (lead.phone_normalized or lead.phone):
                profile = self.db.query(WhatsAppProfile).first()
                if profile:
                    try:
                        self.whatsapp_service.send_message(
                            profile_id=profile.id,
                            recipient=lead.phone_normalized or lead.phone,
                            content=question,
                            idempotency_key=f"tenant-clarification:{lead.id}:{msg.id if msg else uuid.uuid4()}",
                        )
                    except Exception as e:
                        logger.warning(f"Could not send clarification: {e}")
            return {
                "intent": ViewingOperationIntent.UNCLEAR.value,
                "needs_clarification": True,
                "clarification_question": question,
                "viewing_id": None,
            }

        if not viewing:
            return {
                "intent": ViewingOperationIntent.UNRELATED.value,
                "viewing_id": None,
            }

        intent = self.classify_intent(content)

        if intent == ViewingOperationIntent.REQUEST_RESCHEDULE:
            rescheduled_viewing = self.reschedule_service.request_reschedule(
                viewing_id=viewing.id,
                requested_by="TENANT",
                reason=content,
                actor_id=actor_id,
            )
            return {
                "intent": intent.value,
                "viewing_id": str(rescheduled_viewing.id),
                "status": rescheduled_viewing.status.value,
                "action": "RESCHEDULE_INITIATED",
            }

        elif intent == ViewingOperationIntent.CANCEL_VIEWING:
            cancelled_viewing = self.cancellation_service.cancel_viewing(
                viewing_id=viewing.id,
                cancelling_party="TENANT",
                reason_code="TENANT_REQUEST",
                reason_text=content,
                actor_id=actor_id,
            )
            return {
                "intent": intent.value,
                "viewing_id": str(cancelled_viewing.id),
                "status": cancelled_viewing.status.value,
                "action": "VIEWING_CANCELLED",
            }

        elif intent == ViewingOperationIntent.CONFIRM_CURRENT_VIEWING:
            return {
                "intent": intent.value,
                "viewing_id": str(viewing.id),
                "status": viewing.status.value,
                "action": "VIEWING_CONFIRMED_ACK",
            }

        return {
            "intent": intent.value,
            "viewing_id": str(viewing.id),
            "status": viewing.status.value,
            "action": "NO_ACTION",
        }

    async def process_inbound_agent_operation(
        self,
        message_id: uuid.UUID,
        agent_id: uuid.UUID,
        actor_id: str = "property_agent",
        override_viewing_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Processes inbound message from property agent concerning confirmed/active viewings.
        """
        msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
        content = (msg.content or "").strip() if msg else ""

        viewing, needs_clarification, question = self.correlate_viewing_for_agent(
            agent_id=agent_id,
            message_text=content,
            override_viewing_id=override_viewing_id,
        )

        if needs_clarification and question:
            agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == agent_id).first()
            if agent and (agent.phone_normalized or agent.phone):
                profile = self.db.query(WhatsAppProfile).first()
                if profile:
                    try:
                        self.whatsapp_service.send_message(
                            profile_id=profile.id,
                            recipient=agent.phone_normalized or agent.phone,
                            content=question,
                            idempotency_key=f"agent-clarification:{agent.id}:{msg.id if msg else uuid.uuid4()}",
                        )
                    except Exception as e:
                        logger.warning(f"Could not send agent clarification: {e}")
            return {
                "intent": ViewingOperationIntent.UNCLEAR.value,
                "needs_clarification": True,
                "clarification_question": question,
                "viewing_id": None,
            }

        if not viewing:
            return {
                "intent": ViewingOperationIntent.UNRELATED.value,
                "viewing_id": None,
            }

        intent = self.classify_intent(content)

        if intent == ViewingOperationIntent.REQUEST_RESCHEDULE:
            rescheduled_viewing = self.reschedule_service.request_reschedule(
                viewing_id=viewing.id,
                requested_by="PROPERTY_AGENT",
                reason=content,
                actor_id=actor_id,
            )
            return {
                "intent": intent.value,
                "viewing_id": str(rescheduled_viewing.id),
                "status": rescheduled_viewing.status.value,
                "action": "RESCHEDULE_INITIATED",
            }

        elif intent == ViewingOperationIntent.CANCEL_VIEWING:
            cancelled_viewing = self.cancellation_service.cancel_viewing(
                viewing_id=viewing.id,
                cancelling_party="PROPERTY_AGENT",
                reason_code="AGENT_REQUEST",
                reason_text=content,
                actor_id=actor_id,
            )
            return {
                "intent": intent.value,
                "viewing_id": str(cancelled_viewing.id),
                "status": cancelled_viewing.status.value,
                "action": "VIEWING_CANCELLED",
            }

        return {
            "intent": intent.value,
            "viewing_id": str(viewing.id),
            "status": viewing.status.value,
            "action": "NO_ACTION",
        }
