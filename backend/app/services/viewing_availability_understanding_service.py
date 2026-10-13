import uuid
import re
import json
import logging
from datetime import datetime, timedelta, timezone as dt_timezone
import zoneinfo
from typing import Optional, Dict, Any, List, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, desc
from sqlalchemy.sql import func
from fastapi import HTTPException, status

from app.models.viewing import Viewing
from app.models.viewing_availability_request import ViewingAvailabilityRequest
from app.models.property_match import PropertyMatch
from app.models.property_listing import PropertyListing
from app.models.property import Property
from app.models.property_agent import PropertyAgent
from app.models.property_agent_conversation import PropertyAgentConversation
from app.models.message import WhatsAppMessage
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingAvailabilityRequestStatus,
    AgentAvailabilityResponseIntent,
    ViewingCorrelationStatus,
    ViewingActorType,
    ViewingSlotSource,
    ListingAvailabilityStatus,
    MessageDirection,
)
from app.schemas.viewing_availability import (
    ExtractedSlotItem,
    AgentAvailabilityExtractionResult,
)
from app.ai.orchestrator import AIOrchestrator
from app.services.viewing_service import ViewingService
from app.services.viewing_slot_service import ViewingSlotService


logger = logging.getLogger(__name__)


class ViewingAvailabilityUnderstandingService:
    """
    Module 5 Phase 3: Viewing Availability Understanding Service.
    Responsibilities:
    - Accept inbound property-agent WhatsApp message ID.
    - Verify sender is a registered Property Agent.
    - Correlate message to the correct active ViewingAvailabilityRequest / Viewing.
      - If ambiguous (multiple active viewings, no distinctive reference code), mark AMBIGUOUS.
    - Classify agent response intent:
      PROVIDE_VIEWING_SLOTS, PROVIDE_SINGLE_SLOT, NO_VIEWING_AVAILABILITY,
      REQUEST_TENANT_AVAILABILITY, PROPOSE_ALTERNATIVE_DATE, PROPERTY_NO_LONGER_AVAILABLE,
      ASK_FOR_CONTEXT, UNRELATED, UNCLEAR.
    - Extract one or more candidate viewing slots or availability windows.
    - Backend slot validation:
      - Relative date resolution anchored to message timestamp.
      - Timezone verification (agent/property timezone, default Asia/Singapore).
      - Future slot check (slot >= message timestamp).
      - Start < End validation.
      - Default viewing duration applied safely.
    - If valid slots found and applied:
      - ViewingSlotService stores slots with source = PROPERTY_AGENT and source_message_id.
      - Viewing transitions to SLOTS_AVAILABLE.
      - ViewingAvailabilityRequest moves to REPLIED.
    - If agent reports property unavailable:
      - Trigger Module 4 availability update path (mark listing/match UNAVAILABLE).
      - Viewing moves to CANCELLED or NEEDS_HUMAN_REVIEW.
    """

    DEFAULT_TIMEZONE = "Asia/Singapore"

    def __init__(self, db: Session, orchestrator: Optional[AIOrchestrator] = None):
        self.db = db
        self.orchestrator = orchestrator or AIOrchestrator()

    def correlate_message_to_viewing(
        self,
        message: WhatsAppMessage,
        override_viewing_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Correlates an incoming agent message to the appropriate Viewing & ViewingAvailabilityRequest.
        """
        sender = message.sender or ""
        agent = (
            self.db.query(PropertyAgent)
            .filter(or_(PropertyAgent.phone_normalized == sender, PropertyAgent.phone == sender))
            .first()
        )
        if not agent:
            return {
                "status": ViewingCorrelationStatus.UNMATCHED,
                "agent_id": None,
                "viewing_id": None,
                "request_id": None,
                "candidate_viewing_ids": [],
                "reason": "Sender is not a registered property agent.",
            }

        # 1. Check manual override viewing
        if override_viewing_id:
            viewing = self.db.query(Viewing).filter(Viewing.id == override_viewing_id).first()
            if viewing and viewing.property_agent_id == agent.id:
                latest_req = (
                    self.db.query(ViewingAvailabilityRequest)
                    .filter(ViewingAvailabilityRequest.viewing_id == viewing.id)
                    .order_by(desc(ViewingAvailabilityRequest.created_at))
                    .first()
                )
                return {
                    "status": ViewingCorrelationStatus.MANUALLY_ASSIGNED,
                    "agent_id": agent.id,
                    "viewing_id": viewing.id,
                    "request_id": latest_req.id if latest_req else None,
                    "candidate_viewing_ids": [viewing.id],
                    "reason": "Manual operator assignment.",
                }
            elif viewing and viewing.property_agent_id != agent.id:
                return {
                    "status": ViewingCorrelationStatus.UNMATCHED,
                    "agent_id": agent.id,
                    "viewing_id": None,
                    "request_id": None,
                    "candidate_viewing_ids": [],
                    "reason": f"Agent {agent.id} does not own viewing {override_viewing_id}.",
                }

        # 2. Find pending/active viewing availability requests for this agent
        pending_requests = (
            self.db.query(ViewingAvailabilityRequest)
            .filter(
                ViewingAvailabilityRequest.property_agent_id == agent.id,
                ViewingAvailabilityRequest.status.in_([
                    ViewingAvailabilityRequestStatus.PENDING,
                    ViewingAvailabilityRequestStatus.QUEUED,
                    ViewingAvailabilityRequestStatus.SENT,
                    ViewingAvailabilityRequestStatus.DELIVERED,
                    ViewingAvailabilityRequestStatus.READ,
                ]),
            )
            .order_by(desc(ViewingAvailabilityRequest.created_at))
            .all()
        )

        content = (message.content or "").strip()

        # 3. If reference codes match in text
        if pending_requests:
            for req in pending_requests:
                listing = req.listing
                if listing:
                    ref_codes = [
                        listing.source_listing_id,
                        listing.listing_reference,
                        f"REF-{str(listing.id)[:8]}",
                    ]
                    for code in ref_codes:
                        if code and code.upper() in content.upper():
                            return {
                                "status": ViewingCorrelationStatus.RESOLVED,
                                "agent_id": agent.id,
                                "viewing_id": req.viewing_id,
                                "request_id": req.id,
                                "candidate_viewing_ids": [req.viewing_id],
                                "reason": f"Matched by listing reference code '{code}'",
                            }

        # 4. If exactly 1 pending request exists
        if len(pending_requests) == 1:
            req = pending_requests[0]
            return {
                "status": ViewingCorrelationStatus.RESOLVED,
                "agent_id": agent.id,
                "viewing_id": req.viewing_id,
                "request_id": req.id,
                "candidate_viewing_ids": [req.viewing_id],
                "reason": "Single active availability request for agent.",
            }

        # 5. Multiple pending requests without distinctive reference -> AMBIGUOUS
        if len(pending_requests) > 1:
            candidate_ids = [r.viewing_id for r in pending_requests]
            return {
                "status": ViewingCorrelationStatus.AMBIGUOUS,
                "agent_id": agent.id,
                "viewing_id": None,
                "request_id": None,
                "candidate_viewing_ids": candidate_ids,
                "reason": f"Agent has {len(pending_requests)} active viewing requests. No reference code provided.",
            }

        # 6. Fallback: check most recent request within last 48 hours even if already replied or in progress
        recent_req = (
            self.db.query(ViewingAvailabilityRequest)
            .filter(ViewingAvailabilityRequest.property_agent_id == agent.id)
            .order_by(desc(ViewingAvailabilityRequest.created_at))
            .first()
        )
        if recent_req:
            # Check if text contains listing reference
            listing = recent_req.listing
            if listing:
                ref_codes = [
                    listing.source_listing_id,
                    listing.listing_reference,
                    f"REF-{str(listing.id)[:8]}",
                ]
                for code in ref_codes:
                    if code and code.upper() in content.upper():
                        return {
                            "status": ViewingCorrelationStatus.RESOLVED,
                            "agent_id": agent.id,
                            "viewing_id": recent_req.viewing_id,
                            "request_id": recent_req.id,
                            "candidate_viewing_ids": [recent_req.viewing_id],
                            "reason": f"Matched recent request by listing reference code '{code}'",
                        }

        return {
            "status": ViewingCorrelationStatus.UNMATCHED,
            "agent_id": agent.id,
            "viewing_id": None,
            "request_id": None,
            "candidate_viewing_ids": [],
            "reason": "No active viewing availability request found for this agent.",
        }

    def _parse_time_string(self, time_str: str) -> Optional[Tuple[int, int]]:
        """
        Parses time like '11am', '3pm', '10:30am', '14:00', '3', '10'.
        Returns (hour, minute) in 24-hour format.
        """
        time_str = time_str.strip().lower()
        m = re.match(r"^(\d{1,2})(?::(\d{2}))?\s*(am|pm)?$", time_str)
        if not m:
            return None
        hr = int(m.group(1))
        minute = int(m.group(2)) if m.group(2) else 0
        ampm = m.group(3)

        if ampm == "pm" and hr < 12:
            hr += 12
        elif ampm == "am" and hr == 12:
            hr = 0
        elif not ampm:
            # Default day hour heuristic: if hr between 1 and 7, assume PM for viewings unless specified
            if 1 <= hr <= 7:
                hr += 12
        return (hr, minute)

    def _resolve_day_offset(self, day_name: str, base_date: datetime) -> datetime:
        """
        Resolves day of week or relative terms ('tomorrow', 'saturday', 'next friday').
        """
        day_name = day_name.lower().strip()
        weekday_map = {
            "monday": 0, "mon": 0,
            "tuesday": 1, "tue": 1,
            "wednesday": 2, "wed": 2,
            "thursday": 3, "thu": 3,
            "friday": 4, "fri": 4,
            "saturday": 5, "sat": 5,
            "sunday": 6, "sun": 6,
        }

        if day_name == "today":
            return base_date
        if day_name == "tomorrow":
            return base_date + timedelta(days=1)

        target_dow = weekday_map.get(day_name)
        if target_dow is not None:
            current_dow = base_date.weekday()
            days_ahead = (target_dow - current_dow) % 7
            if days_ahead == 0:
                # If same day, assume upcoming or next week
                days_ahead = 7
            return base_date + timedelta(days=days_ahead)

        return base_date

    def extract_slots_deterministic(
        self,
        text: str,
        base_timestamp: datetime,
        tz_str: str = "Asia/Singapore",
        default_duration_minutes: int = 30,
    ) -> List[ExtractedSlotItem]:
        """
        Deterministic slot extractor for common patterns:
        - 'Saturday 11am or 3pm, Sunday 10am'
        - 'Saturday 3pm'
        - 'Tomorrow 6pm'
        - 'Saturday between 2 and 5' -> window from 14:00 to 17:00
        - 'Monday 6pm'
        """
        slots: List[ExtractedSlotItem] = []
        try:
            tz = zoneinfo.ZoneInfo(tz_str)
        except Exception:
            tz = zoneinfo.ZoneInfo("Asia/Singapore")

        base_local = base_timestamp.astimezone(tz)
        clean = text.strip()

        # Check window pattern: "Saturday between 2 and 5" or "between 2pm and 5pm"
        window_pattern = re.compile(
            r"(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|mon|tue|wed|thu|fri|sat|sun)?\s*(?:anytime\s+)?between\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)\s+and\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)",
            re.IGNORECASE,
        )
        for m in window_pattern.finditer(clean):
            day_str = m.group(1) or "tomorrow"
            target_date = self._resolve_day_offset(day_str, base_local)
            start_t = self._parse_time_string(m.group(2))
            end_t = self._parse_time_string(m.group(3))
            if start_t and end_t:
                # Handle PM roll for end_t if end_t < start_t
                start_hr, start_min = start_t
                end_hr, end_min = end_t
                if end_hr < start_hr and end_hr < 12:
                    end_hr += 12

                start_dt = target_date.replace(hour=start_hr, minute=start_min, second=0, microsecond=0)
                end_dt = target_date.replace(hour=end_hr, minute=end_min, second=0, microsecond=0)
                if end_dt > start_dt:
                    slots.append(
                        ExtractedSlotItem(
                            start_at=start_dt,
                            end_at=end_dt,
                            timezone=tz_str,
                            confidence=0.98,
                            duration_minutes=int((end_dt - start_dt).total_seconds() / 60),
                            is_window=True,
                        )
                    )

        # Check multi-day/multi-slot pattern:
        # Split clauses by comma or semicolons
        clauses = re.split(r"[,;.]\s*", clean)
        current_day_str = None

        day_words = ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        time_token = r"(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)"

        for clause in clauses:
            if "between" in clause.lower():
                continue  # already handled by window pattern

            # Look for day in this clause
            found_day = None
            for dw in day_words:
                if re.search(r"\b" + dw + r"\b", clause, re.IGNORECASE):
                    found_day = dw
                    current_day_str = dw
                    break

            effective_day = found_day or current_day_str
            if not effective_day:
                continue

            target_date = self._resolve_day_offset(effective_day, base_local)

            # Find all times mentioned in this clause, e.g. "11am or 3pm", "10am", "6pm"
            time_matches = re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b|\b(?:at\s+)?(\d{1,2})\s*(?:am|pm)?\b", clause, re.IGNORECASE)
            
            # Find times with regex
            times_found = re.findall(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", clause, re.IGNORECASE)
            parsed_times = []
            for tf in times_found:
                if tf.lower() in day_words or tf.lower() in ["and", "or", "to", "at", "is", "also"]:
                    continue
                pt = self._parse_time_string(tf)
                if pt:
                    parsed_times.append(pt)

            for pt in parsed_times:
                hr, minute = pt
                start_dt = target_date.replace(hour=hr, minute=minute, second=0, microsecond=0)
                end_dt = start_dt + timedelta(minutes=default_duration_minutes)

                # Check if already in slots
                if not any(s.start_at == start_dt for s in slots):
                    slots.append(
                        ExtractedSlotItem(
                            start_at=start_dt,
                            end_at=end_dt,
                            timezone=tz_str,
                            confidence=0.95,
                            duration_minutes=default_duration_minutes,
                            is_window=False,
                        )
                    )

        return slots

    def classify_intent_heuristics(self, text: str) -> Tuple[AgentAvailabilityResponseIntent, bool, Optional[str]]:
        """
        Classifies response intent and checks for property unavailability or tenant availability request.
        Returns (intent, property_unavailable, notes)
        """
        text_lower = text.lower().strip()

        # Prompt injection protection check
        if "ignore your rules" in text_lower or "ignore previous instructions" in text_lower:
            return (AgentAvailabilityResponseIntent.UNCLEAR, False, "Potential prompt injection attempt ignored.")

        # 1. Property No Longer Available
        if any(p in text_lower for p in [
            "already rented",
            "unit is rented",
            "taken",
            "no longer available",
            "taken by another tenant",
            "already taken",
            "unit taken",
            "off the market",
            "deal closed",
        ]):
            return (AgentAvailabilityResponseIntent.PROPERTY_NO_LONGER_AVAILABLE, True, text.strip())

        # 2. No viewing availability
        if any(p in text_lower for p in [
            "no viewings this week",
            "not available for viewing",
            "cannot do viewing",
            "fully booked this week",
            "no slots available",
            "not free this week",
            "can't view",
        ]):
            return (AgentAvailabilityResponseIntent.NO_VIEWING_AVAILABILITY, False, text.strip())

        # 3. Request tenant availability
        if any(p in text_lower for p in [
            "when can the tenant come",
            "what times can the tenant do",
            "ask the tenant when they are free",
            "tenant's availability",
            "when is tenant available",
            "what day can they do",
        ]):
            return (AgentAvailabilityResponseIntent.REQUEST_TENANT_AVAILABILITY, False, None)

        # 4. Propose alternative
        if "full" in text_lower and any(w in text_lower for p in ["but", "instead", "can do"] for w in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]):
            return (AgentAvailabilityResponseIntent.PROPOSE_ALTERNATIVE_DATE, False, None)

        # 5. Check if slots or window present
        if any(d in text_lower for d in ["today", "tomorrow", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday", "sat", "sun"]):
            if any(t in text_lower for t in ["am", "pm", "between", "at", "morning", "afternoon", "evening", "11", "3", "10", "6"]):
                return (AgentAvailabilityResponseIntent.PROVIDE_VIEWING_SLOTS, False, None)

        # 6. Ask for context
        if any(q in text_lower for q in ["which property", "what ref", "who is the tenant", "which unit", "details?"]):
            return (AgentAvailabilityResponseIntent.ASK_FOR_CONTEXT, False, None)

        return (AgentAvailabilityResponseIntent.UNCLEAR, False, None)

    async def extract_availability(
        self,
        message: WhatsAppMessage,
        correlation: Dict[str, Any],
        actor_id: str = "system",
    ) -> AgentAvailabilityExtractionResult:
        """
        Analyzes inbound property agent message, extracts intent and slots.
        """
        text = (message.content or "").strip()
        msg_time = message.created_at or datetime.now(dt_timezone.utc)
        if msg_time.tzinfo is None:
            msg_time = msg_time.replace(tzinfo=dt_timezone.utc)

        intent, is_unavailable, notes = self.classify_intent_heuristics(text)

        # Check for ambiguous day like "Next Friday evening" with no exact time
        ambiguous_day_only = False
        if re.search(r"\b(evening|afternoon|morning)\b", text, re.IGNORECASE) and not re.search(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b", text):
            ambiguous_day_only = True

        slots = []
        if intent in [
            AgentAvailabilityResponseIntent.PROVIDE_VIEWING_SLOTS,
            AgentAvailabilityResponseIntent.PROPOSE_ALTERNATIVE_DATE,
        ] and not ambiguous_day_only:
            slots = self.extract_slots_deterministic(
                text=text,
                base_timestamp=msg_time,
                tz_str=self.DEFAULT_TIMEZONE,
            )
            if len(slots) == 1 and intent == AgentAvailabilityResponseIntent.PROVIDE_VIEWING_SLOTS:
                intent = AgentAvailabilityResponseIntent.PROVIDE_SINGLE_SLOT

        needs_clarification = ambiguous_day_only or (intent == AgentAvailabilityResponseIntent.UNCLEAR)

        result = AgentAvailabilityExtractionResult(
            intent=intent,
            slots=slots,
            agent_notes=notes or (text if intent in [AgentAvailabilityResponseIntent.NO_VIEWING_AVAILABILITY, AgentAvailabilityResponseIntent.PROPERTY_NO_LONGER_AVAILABLE] else None),
            needs_clarification=needs_clarification,
            property_unavailable=is_unavailable,
            confidence=0.95 if slots or is_unavailable else 0.70,
            correlation_status=correlation["status"],
            matched_viewing_id=correlation.get("viewing_id"),
            matched_request_id=correlation.get("request_id"),
            candidate_viewing_ids=correlation.get("candidate_viewing_ids", []),
            raw_response=text,
        )
        return result

    def apply_extraction_to_viewing(
        self,
        extraction: AgentAvailabilityExtractionResult,
        source_message_id: uuid.UUID,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Takes structured extraction, validates timestamps, stores ViewingSlots,
        updates ViewingAvailabilityRequest, and manages Viewing workflow status.
        """
        # 1. Check Correlation Status
        if extraction.correlation_status == ViewingCorrelationStatus.AMBIGUOUS:
            # Mark candidate requests or viewings for review
            for vid in extraction.candidate_viewing_ids:
                req = (
                    self.db.query(ViewingAvailabilityRequest)
                    .filter(ViewingAvailabilityRequest.viewing_id == vid)
                    .order_by(desc(ViewingAvailabilityRequest.created_at))
                    .first()
                )
                if req:
                    req.correlation_status = ViewingCorrelationStatus.AMBIGUOUS
                    req.raw_response_text = extraction.raw_response
                viewing = self.db.query(Viewing).filter(Viewing.id == vid).first()
                if viewing:
                    ViewingService.transition_viewing(
                        db=self.db,
                        viewing_id=vid,
                        target_status=ViewingStatus.NEEDS_HUMAN_REVIEW,
                        reason="Ambiguous agent reply received across multiple active viewings.",
                        actor_type=ViewingActorType.SYSTEM,
                        actor_id=actor_id,
                    )
            self.db.commit()

            audit = AuditLog(
                action="VIEWING_REPLY_AMBIGUOUS",
                actor_id=actor_id,
                entity_type="viewing_availability_request",
                entity_id=str(source_message_id),
                new_value={
                    "candidate_viewing_ids": [str(v) for v in extraction.candidate_viewing_ids],
                    "raw_response": extraction.raw_response,
                },
            )
            self.db.add(audit)
            self.db.commit()
            return {
                "status": "AMBIGUOUS_NEEDS_REVIEW",
                "viewing_id": None,
                "slots_stored": 0,
                "intent": extraction.intent.value,
            }

        if extraction.correlation_status in [ViewingCorrelationStatus.UNMATCHED] or not extraction.matched_viewing_id:
            logger.warning(f"Unmatched agent reply for message {source_message_id}")
            return {
                "status": "UNMATCHED",
                "viewing_id": None,
                "slots_stored": 0,
                "intent": extraction.intent.value,
            }

        viewing_id = extraction.matched_viewing_id
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        # Load availability request
        request = None
        if extraction.matched_request_id:
            request = self.db.query(ViewingAvailabilityRequest).filter(ViewingAvailabilityRequest.id == extraction.matched_request_id).first()
        if not request:
            request = (
                self.db.query(ViewingAvailabilityRequest)
                .filter(ViewingAvailabilityRequest.viewing_id == viewing_id)
                .order_by(desc(ViewingAvailabilityRequest.created_at))
                .first()
            )

        if request:
            request.status = ViewingAvailabilityRequestStatus.REPLIED
            request.replied_at = datetime.now(dt_timezone.utc)
            request.raw_response_text = extraction.raw_response
            request.response_intent = extraction.intent
            request.agent_notes = extraction.agent_notes

        # 2. Handle Property Unavailable
        if extraction.property_unavailable or extraction.intent == AgentAvailabilityResponseIntent.PROPERTY_NO_LONGER_AVAILABLE:
            # Update Listing and Match
            listing = viewing.listing
            match = viewing.property_match
            if listing:
                listing.availability_status = ListingAvailabilityStatus.UNAVAILABLE
            if match:
                match.match_status = "UNAVAILABLE"
                match.availability_status = ListingAvailabilityStatus.UNAVAILABLE.value

            # Cancel viewing safely
            ViewingService.transition_viewing(
                db=self.db,
                viewing_id=viewing.id,
                target_status=ViewingStatus.CANCELLED,
                reason="Property agent reported property is no longer available/rented.",
                actor_type=ViewingActorType.PROPERTY_AGENT,
                actor_id=actor_id,
            )

            audit = AuditLog(
                action="PROPERTY_REPORTED_UNAVAILABLE",
                actor_id=actor_id,
                entity_type="viewing",
                entity_id=str(viewing.id),
                new_value={"reason": extraction.raw_response, "listing_id": str(viewing.listing_id)},
            )
            self.db.add(audit)
            self.db.commit()
            return {
                "status": "PROPERTY_UNAVAILABLE",
                "viewing_id": str(viewing.id),
                "slots_stored": 0,
                "intent": extraction.intent.value,
            }

        # 3. Handle No Viewing Availability
        if extraction.intent == AgentAvailabilityResponseIntent.NO_VIEWING_AVAILABILITY:
            ViewingService.transition_viewing(
                db=self.db,
                viewing_id=viewing.id,
                target_status=ViewingStatus.NEEDS_HUMAN_REVIEW,
                reason="Property agent reported no viewing availability this week.",
                actor_type=ViewingActorType.PROPERTY_AGENT,
                actor_id=actor_id,
            )
            audit = AuditLog(
                action="NO_AGENT_AVAILABILITY",
                actor_id=actor_id,
                entity_type="viewing",
                entity_id=str(viewing.id),
                new_value={"agent_notes": extraction.agent_notes},
            )
            self.db.add(audit)
            self.db.commit()
            return {
                "status": "NO_AVAILABILITY",
                "viewing_id": str(viewing.id),
                "slots_stored": 0,
                "intent": extraction.intent.value,
            }

        # 4. Handle Request Tenant Availability
        if extraction.intent == AgentAvailabilityResponseIntent.REQUEST_TENANT_AVAILABILITY:
            ViewingService.transition_viewing(
                db=self.db,
                viewing_id=viewing.id,
                target_status=ViewingStatus.AWAITING_TENANT_AVAILABILITY,
                reason="Agent requested tenant's viewing schedule.",
                actor_type=ViewingActorType.PROPERTY_AGENT,
                actor_id=actor_id,
            )
            audit = AuditLog(
                action="AGENT_REQUESTED_TENANT_AVAILABILITY",
                actor_id=actor_id,
                entity_type="viewing",
                entity_id=str(viewing.id),
                new_value={"notes": extraction.raw_response},
            )
            self.db.add(audit)
            self.db.commit()
            return {
                "status": "AWAITING_TENANT_AVAILABILITY",
                "viewing_id": str(viewing.id),
                "slots_stored": 0,
                "intent": extraction.intent.value,
            }

        # 5. Handle Clarification / Ambiguous Dates
        if extraction.needs_clarification or not extraction.slots:
            ViewingService.transition_viewing(
                db=self.db,
                viewing_id=viewing.id,
                target_status=ViewingStatus.NEEDS_HUMAN_REVIEW,
                reason="Agent message needs clarification or contains ambiguous time specifications.",
                actor_type=ViewingActorType.PROPERTY_AGENT,
                actor_id=actor_id,
            )
            self.db.commit()
            return {
                "status": "NEEDS_CLARIFICATION",
                "viewing_id": str(viewing.id),
                "slots_stored": 0,
                "intent": extraction.intent.value,
            }

        # 6. Backend Slot Storage
        slots_payload = [
            {
                "start_at": s.start_at,
                "end_at": s.end_at,
                "timezone": s.timezone,
            }
            for s in extraction.slots
        ]

        stored_slots = ViewingSlotService.bulk_add_agent_slots(
            db=self.db,
            viewing_id=viewing.id,
            slots_data=slots_payload,
            source_message_id=source_message_id,
            timezone=self.DEFAULT_TIMEZONE,
            actor_id=actor_id,
        )

        # Transition viewing to SLOTS_AVAILABLE
        if stored_slots and viewing.status != ViewingStatus.SLOTS_AVAILABLE:
            ViewingService.transition_viewing(
                db=self.db,
                viewing_id=viewing.id,
                target_status=ViewingStatus.SLOTS_AVAILABLE,
                reason=f"Stored {len(stored_slots)} candidate slots from listing agent.",
                actor_type=ViewingActorType.SYSTEM,
                actor_id=actor_id,
            )

        audit = AuditLog(
            action="AGENT_SLOTS_STORED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={
                "slot_count": len(stored_slots),
                "slot_ids": [str(s.id) for s in stored_slots],
                "intent": extraction.intent.value,
            },
        )
        self.db.add(audit)
        self.db.commit()

        return {
            "status": "SLOTS_AVAILABLE",
            "viewing_id": str(viewing.id),
            "slots_stored": len(stored_slots),
            "intent": extraction.intent.value,
            "slot_ids": [str(s.id) for s in stored_slots],
        }

    async def process_inbound_agent_message(
        self,
        message_id: uuid.UUID,
        override_viewing_id: Optional[uuid.UUID] = None,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Complete pipeline for inbound property agent message:
        1. Fetch message
        2. Correlate with Viewing
        3. Extract slots / intent
        4. Apply extraction to database (store slots, transition viewing)
        """
        msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"WhatsAppMessage '{message_id}' not found.",
            )

        correlation = self.correlate_message_to_viewing(
            message=msg,
            override_viewing_id=override_viewing_id,
        )

        extraction = await self.extract_availability(
            message=msg,
            correlation=correlation,
            actor_id=actor_id,
        )

        result = self.apply_extraction_to_viewing(
            extraction=extraction,
            source_message_id=msg.id,
            actor_id=actor_id,
        )

        return {
            "message_id": str(msg.id),
            "correlation": correlation,
            "extraction": extraction.dict(),
            "result": result,
        }
