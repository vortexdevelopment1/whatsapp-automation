"""
Tenant Viewing Availability Understanding Service - Module 5 Phase 4
Analyzes inbound tenant messages or interactive button clicks during viewing scheduling.
Extracts structured availability, classifies intents, resolves multi-viewing correlation,
runs deterministic slot matching, and proposes candidate viewing slots without confirming.
"""
import uuid
import logging
import re
import zoneinfo
from datetime import datetime, timedelta, timezone as dt_timezone
from typing import Optional, Dict, Any, List, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.lead import Lead
from app.models.message import WhatsAppMessage
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_match import PropertyMatch
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingSlotSource,
    ViewingSlotStatus,
    ViewingEventType,
    ViewingActorType,
    TenantAvailabilityResponseIntent,
    SlotMatchType,
    PropertyStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
)
from app.schemas.viewing_availability import (
    TenantAvailabilityUnderstandingResult,
    TenantAvailabilityWindowItem,
    MutualSlotMatchItem,
    ViewingSlotMatchingResult,
)
from app.services.viewing_slot_matching_service import ViewingSlotMatchingService
from app.services.viewing_service import ViewingService
from app.services.viewing_slot_service import ViewingSlotService
from app.services.viewing_state_machine import ViewingStateMachine
from app.services.viewing_config import ViewingConfig

logger = logging.getLogger(__name__)


class TenantViewingAvailabilityUnderstandingService:
    """
    Understands tenant responses regarding viewing availability and slot choices.
    Strict safety constraints:
    - AI / NLP NEVER performs slot matching or confirms bookings.
    - Resolves multi-viewing ambiguity safely (asks for clarification if 2+ viewings compete).
    - Prevents selecting expired or invalid agent slots.
    - Transitions viewing at most to SLOT_PROPOSED. Phase 5 handles confirmation.
    """

    DAY_MAPPING = {
        "monday": 0, "mon": 0,
        "tuesday": 1, "tue": 1, "tues": 1,
        "wednesday": 2, "wed": 2,
        "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
        "friday": 4, "fri": 4,
        "saturday": 5, "sat": 5,
        "sunday": 6, "sun": 6,
    }

    def __init__(self, db: Session):
        self.db = db
        self.slot_matching_service = ViewingSlotMatchingService(db)

    def correlate_viewing_for_lead(
        self,
        lead_id: uuid.UUID,
        message_text: str,
        override_viewing_id: Optional[uuid.UUID] = None,
        interactive_payload: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[Viewing], bool, Optional[str]]:
        """
        Correlates tenant inbound message to a viewing.
        Returns (viewing, needs_clarification, clarification_question).
        """
        # 1. Interactive Payload
        if interactive_payload and interactive_payload.get("viewing_id"):
            try:
                v_id = uuid.UUID(str(interactive_payload["viewing_id"]))
                viewing = self.db.query(Viewing).filter(Viewing.id == v_id, Viewing.lead_id == lead_id).first()
                if viewing:
                    return viewing, False, None
            except Exception:
                pass

        # 2. Manual Override
        if override_viewing_id:
            viewing = self.db.query(Viewing).filter(Viewing.id == override_viewing_id, Viewing.lead_id == lead_id).first()
            if viewing:
                return viewing, False, None

        # 3. Find active viewings awaiting availability or slots available
        active_viewings = (
            self.db.query(Viewing)
            .filter(
                Viewing.lead_id == lead_id,
                Viewing.status.in_([
                    ViewingStatus.SLOTS_AVAILABLE,
                    ViewingStatus.AWAITING_TENANT_AVAILABILITY,
                    ViewingStatus.SLOT_PROPOSED,
                ]),
            )
            .order_by(desc(Viewing.updated_at))
            .all()
        )

        if not active_viewings:
            # Fallback to any active viewing
            any_active = (
                self.db.query(Viewing)
                .filter(
                    Viewing.lead_id == lead_id,
                    Viewing.status.notin_([
                        ViewingStatus.CANCELLED,
                        ViewingStatus.COMPLETED,
                        ViewingStatus.REJECTED,
                    ]),
                )
                .order_by(desc(Viewing.updated_at))
                .first()
            )
            return any_active, False, None

        if len(active_viewings) == 1:
            return active_viewings[0], False, None

        # Multiple active viewings: check if text references a specific property
        text_lower = message_text.lower()
        matched_viewing = None
        for v in active_viewings:
            prop_title = (getattr(v.property, "canonical_name", None) or getattr(v.property, "building_name", None) or "").lower()
            prop_address = (getattr(v.property, "address_line_1", None) or "").lower()
            if (prop_title and prop_title in text_lower) or (prop_address and prop_address in text_lower):
                matched_viewing = v
                break

        if matched_viewing:
            return matched_viewing, False, None

        # Ambiguous multiple active viewings!
        prop_names = [f"'{getattr(v.property, 'canonical_name', 'Property')}'" for v in active_viewings if v.property]
        names_str = " or ".join(prop_names) if prop_names else "your requested properties"
        clarification = f"You have viewings scheduled for {names_str}. Which property is your reply for?"
        return None, True, clarification

    def classify_tenant_intent(
        self,
        text: str,
        interactive_payload: Optional[Dict[str, Any]] = None,
        available_slots: Optional[List[ViewingSlot]] = None,
    ) -> TenantAvailabilityResponseIntent:
        """
        Classifies tenant intent from text or interactive button clicks.
        """
        text_lower = text.lower().strip()

        # 1. Interactive Button Click or Slot ID Reference
        if interactive_payload and (interactive_payload.get("slot_id") or interactive_payload.get("action") == "select_slot"):
            return TenantAvailabilityResponseIntent.SELECT_SLOT

        # 2. Cancellation
        if any(p in text_lower for p in [
            "don't want to view", "dont want to view", "cancel viewing", "cancel the viewing",
            "cancel it", "no longer interested", "not interested anymore", "stop viewing",
            "i don't want to view this anymore", "i dont want to view this anymore"
        ]):
            return TenantAvailabilityResponseIntent.CANCEL_VIEWING_REQUEST

        # 3. None of these work
        if any(p in text_lower for p in [
            "none of these", "none of them", "neither works", "none work", "none of those",
            "busy all weekend", "cannot make any of these", "can't make any", "not free at these times"
        ]):
            return TenantAvailabilityResponseIntent.NONE_OF_THESE_WORK

        # 4. Request other slot / alternative
        if any(p in text_lower for p in [
            "do they have anything", "any other times", "other slot", "anything in the evening",
            "any weekday", "any morning", "can we do next week", "any other day", "is there another time"
        ]):
            return TenantAvailabilityResponseIntent.REQUEST_OTHER_SLOT

        # 5. Direct Option Selection (e.g., "1", "option 1", "first one", "#2")
        if re.match(r"^(?:option\s+|#)?([1-5])(?:\s+works|\s+please)?$", text_lower):
            return TenantAvailabilityResponseIntent.SELECT_SLOT
        if any(p in text_lower for p in ["first one", "second one", "third one"]):
            return TenantAvailabilityResponseIntent.SELECT_SLOT

        # 6. Specific slot acceptance (e.g. "Saturday 3 works", "3pm works", "Saturday 11 works")
        if any(w in text_lower for w in ["works", "works for me", "is good", "sounds good", "perfect", "suit me", "suits me"]):
            return TenantAvailabilityResponseIntent.SELECT_SLOT

        # 7. Property Question during scheduling
        if any(p in text_lower for p in [
            "where is it", "what is the rent", "which property", "how much is the rent",
            "what's the address", "can you tell me the location"
        ]):
            return TenantAvailabilityResponseIntent.ASK_VIEWING_QUESTION

        # 8. General availability provided
        if any(w in text_lower for w in ["between", "after", "before", "around", "morning", "afternoon", "evening", "tomorrow", "weekend", "saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday"]):
            return TenantAvailabilityResponseIntent.PROVIDE_AVAILABILITY

        return TenantAvailabilityResponseIntent.UNCLEAR

    def _resolve_relative_day(self, day_text: str, base_dt: datetime) -> datetime:
        day_text = day_text.lower().strip()
        if day_text == "today":
            return base_dt
        if day_text == "tomorrow":
            return base_dt + timedelta(days=1)
        if day_text in self.DAY_MAPPING:
            target_weekday = self.DAY_MAPPING[day_text]
            current_weekday = base_dt.weekday()
            days_ahead = (target_weekday - current_weekday) % 7
            if days_ahead == 0:
                days_ahead = 7
            return base_dt + timedelta(days=days_ahead)
        return base_dt

    def extract_availability_windows(
        self,
        text: str,
        timezone_str: str = "Asia/Singapore",
    ) -> List[TenantAvailabilityWindowItem]:
        """
        Extracts structured tenant availability windows from text.
        Handles:
        - "Saturday between 2 and 5" -> 14:00 - 17:00
        - "Sunday morning" -> 09:00 - 12:00
        - "Anytime after 2 tomorrow" -> 14:00 - 18:00
        - "Weekdays after 6" -> Mon-Fri 18:00 - 21:00
        - "Saturday 3pm" -> 15:00 - 15:30
        """
        windows: List[TenantAvailabilityWindowItem] = []
        now_local = datetime.now(zoneinfo.ZoneInfo(timezone_str))
        text_lower = text.lower()

        # Find day referenced
        day_str = "today"
        for d in ["tomorrow", "today", "saturday", "sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "sat", "sun"]:
            if re.search(r"\b" + d + r"\b", text_lower):
                day_str = d
                break

        target_date = self._resolve_relative_day(day_str, now_local)

        # Pattern 1: Between X and Y (e.g. "between 2 and 5", "between 2pm and 5pm")
        between_match = re.search(r"between\s+(\d{1,2})(?::\d{2})?\s*(am|pm)?\s+and\s+(\d{1,2})(?::\d{2})?\s*(am|pm)?", text_lower)
        if between_match:
            h1 = int(between_match.group(1))
            mer1 = between_match.group(2)
            h2 = int(between_match.group(3))
            mer2 = between_match.group(4) or mer1 or "pm"

            if mer1 == "pm" and h1 < 12:
                h1 += 12
            elif not mer1 and mer2 == "pm" and h1 < 12 and h1 <= h2:
                h1 += 12  # "between 2 and 5pm"
            if mer2 == "pm" and h2 < 12:
                h2 += 12

            start_dt = target_date.replace(hour=h1, minute=0, second=0, microsecond=0)
            end_dt = target_date.replace(hour=h2, minute=0, second=0, microsecond=0)
            windows.append(
                TenantAvailabilityWindowItem(
                    start_at=start_dt,
                    end_at=end_dt,
                    timezone=timezone_str,
                    confidence=0.95,
                )
            )
            return windows

        # Pattern 2: After X (e.g. "after 2", "after 2pm", "after 6")
        after_match = re.search(r"after\s+(\d{1,2})(?::\d{2})?\s*(am|pm)?", text_lower)
        if after_match:
            h = int(after_match.group(1))
            mer = after_match.group(2) or ("pm" if h < 9 else "am")
            if mer == "pm" and h < 12:
                h += 12
            start_dt = target_date.replace(hour=h, minute=0, second=0, microsecond=0)
            end_dt = start_dt + timedelta(hours=3)  # default 3 hour window
            windows.append(
                TenantAvailabilityWindowItem(
                    start_at=start_dt,
                    end_at=end_dt,
                    timezone=timezone_str,
                    confidence=0.90,
                )
            )
            return windows

        # Pattern 3: Broad part of day (morning, afternoon, evening)
        if "morning" in text_lower:
            windows.append(
                TenantAvailabilityWindowItem(
                    start_at=target_date.replace(hour=9, minute=0, second=0, microsecond=0),
                    end_at=target_date.replace(hour=12, minute=0, second=0, microsecond=0),
                    timezone=timezone_str,
                    confidence=0.90,
                )
            )
            return windows
        if "afternoon" in text_lower:
            windows.append(
                TenantAvailabilityWindowItem(
                    start_at=target_date.replace(hour=13, minute=0, second=0, microsecond=0),
                    end_at=target_date.replace(hour=17, minute=0, second=0, microsecond=0),
                    timezone=timezone_str,
                    confidence=0.90,
                )
            )
            return windows
        if "evening" in text_lower:
            windows.append(
                TenantAvailabilityWindowItem(
                    start_at=target_date.replace(hour=18, minute=0, second=0, microsecond=0),
                    end_at=target_date.replace(hour=21, minute=0, second=0, microsecond=0),
                    timezone=timezone_str,
                    confidence=0.90,
                )
            )
            return windows

        # Pattern 4: Single time point (e.g. "Saturday 3", "3pm works", "11:00 am")
        single_time_match = re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", text_lower)
        if single_time_match:
            h = int(single_time_match.group(1))
            m = int(single_time_match.group(2) or 0)
            mer = single_time_match.group(3) or ("pm" if 1 <= h <= 6 else "am")
            if mer == "pm" and h < 12:
                h += 12
            start_dt = target_date.replace(hour=h, minute=m, second=0, microsecond=0)
            end_dt = start_dt + timedelta(minutes=30)
            windows.append(
                TenantAvailabilityWindowItem(
                    start_at=start_dt,
                    end_at=end_dt,
                    timezone=timezone_str,
                    confidence=0.95,
                )
            )

        return windows

    def resolve_selected_slot_from_text(
        self,
        text: str,
        available_slots: List[ViewingSlot],
        viewing_tz: str = "Asia/Singapore",
    ) -> Optional[ViewingSlot]:
        """
        Resolves which agent slot the tenant picked via text selection:
        - "1" or "option 1" -> 1st available slot
        - "Saturday 3" -> agent slot on Saturday at 15:00
        - "Sunday morning" / "10am" -> agent slot at 10:00
        """
        if not available_slots:
            return None

        text_lower = text.lower().strip()

        # Check numeric index (1-indexed)
        idx_match = re.match(r"^(?:option\s+|#)?([1-5])(?:\s+works|\s+please)?$", text_lower)
        if idx_match:
            idx = int(idx_match.group(1)) - 1
            if 0 <= idx < len(available_slots):
                return available_slots[idx]

        if "first one" in text_lower and len(available_slots) >= 1:
            return available_slots[0]
        if "second one" in text_lower and len(available_slots) >= 2:
            return available_slots[1]
        if "third one" in text_lower and len(available_slots) >= 3:
            return available_slots[2]

        # Check by matching day and hour
        for s in available_slots:
            s_dt = ViewingSlotMatchingService.to_display_tz(
                ViewingSlotMatchingService.to_utc(s.start_at, s.timezone),
                viewing_tz,
            )
            day_name = s_dt.strftime("%A").lower()
            hour_12 = s_dt.strftime("%I").lstrip("0")
            hour_str = f"{hour_12}pm" if s_dt.hour >= 12 else f"{hour_12}am"

            # Check if text contains day AND time (or just time if day matches or only 1 slot has that time)
            if (day_name in text_lower or day_name[:3] in text_lower) and (
                hour_12 in text_lower or hour_str in text_lower or f"{s_dt.hour}" in text_lower
            ):
                return s
            if hour_str in text_lower or f"{hour_12}:00" in text_lower:
                return s

        return None

    def propose_candidate_slot(
        self,
        viewing: Viewing,
        candidate_slot: Union[ViewingSlot, MutualSlotMatchItem],
        actor_id: str = "tenant",
        reason: Optional[str] = None,
    ) -> ViewingSlot:
        """
        Atomically proposes a candidate slot.
        Revalidates:
        - Viewing is active (not CANCELLED/COMPLETED)
        - Property & listing active and available
        - Candidate slot is valid and not expired
        - Enforces double-selection protection (at most one PROPOSED slot per viewing)
        - Transitions viewing to ViewingStatus.SLOT_PROPOSED
        - CRITICAL: Does NOT transition to CONFIRMED.
        """
        now_utc = datetime.now(dt_timezone.utc)

        # 1. Revalidate Property & Listing state
        prop = self.db.query(Property).filter(Property.id == viewing.property_id).first()
        if not prop or prop.status == PropertyStatus.INACTIVE:
            raise ValueError("Property is inactive or unavailable. Cannot propose viewing slot.")

        listing = self.db.query(PropertyListing).filter(PropertyListing.id == viewing.listing_id).first()
        if not listing or listing.listing_status in [PropertyListingStatus.INACTIVE, PropertyListingStatus.REMOVED, PropertyListingStatus.EXPIRED] or listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE:
            raise ValueError("Property listing is no longer available. Cannot propose viewing slot.")

        # 2. Revalidate Viewing state
        if viewing.status in [ViewingStatus.CANCELLED, ViewingStatus.COMPLETED, ViewingStatus.REJECTED]:
            raise ValueError(f"Viewing is inactive (status={viewing.status.value}).")

        # 3. Resolve target slot
        slot_record: Optional[ViewingSlot] = None
        if isinstance(candidate_slot, ViewingSlot):
            slot_record = candidate_slot
        else:
            if candidate_slot.agent_slot_id:
                slot_record = self.db.query(ViewingSlot).filter(ViewingSlot.id == candidate_slot.agent_slot_id).first()

        if not slot_record:
            # Create a mutual slot in viewing_slots if synthesized from overlap
            start_utc = ViewingSlotMatchingService.to_utc(candidate_slot.start_at, candidate_slot.timezone)
            end_utc = ViewingSlotMatchingService.to_utc(candidate_slot.end_at, candidate_slot.timezone)
            slot_record = ViewingSlot(
                viewing_id=viewing.id,
                source=ViewingSlotSource.SYSTEM,
                start_at=start_utc,
                end_at=end_utc,
                timezone=candidate_slot.timezone,
                status=ViewingSlotStatus.PROPOSED,
                is_mutual_match=True,
            )
            self.db.add(slot_record)
            self.db.flush()

        # 4. Check expired
        slot_start_utc = ViewingSlotMatchingService.to_utc(slot_record.start_at, slot_record.timezone)
        if slot_start_utc <= now_utc:
            slot_record.status = ViewingSlotStatus.EXPIRED
            self.db.commit()
            raise ValueError("Selected viewing slot has expired.")

        # 5. Double-selection protection: Demote any other proposed slots for this viewing
        prev_proposed = (
            self.db.query(ViewingSlot)
            .filter(
                ViewingSlot.viewing_id == viewing.id,
                ViewingSlot.id != slot_record.id,
                ViewingSlot.status.in_([ViewingSlotStatus.PROPOSED, ViewingSlotStatus.SELECTED]),
            )
            .all()
        )
        for ps in prev_proposed:
            ps.status = ViewingSlotStatus.AVAILABLE
            ps.is_mutual_match = False

        # Mark this slot as PROPOSED
        slot_record.status = ViewingSlotStatus.PROPOSED
        slot_record.is_mutual_match = True

        # Update Viewing scheduled times
        old_status = viewing.status.value
        viewing.scheduled_start_at = slot_record.start_at
        viewing.scheduled_end_at = slot_record.end_at
        viewing.timezone = slot_record.timezone

        # Move viewing status to SLOT_PROPOSED
        if ViewingStateMachine.can_transition(viewing.status, ViewingStatus.SLOT_PROPOSED):
            viewing.status = ViewingStatus.SLOT_PROPOSED

        # Audit events
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.STATUS_CHANGED,
            old_status=old_status,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.TENANT if actor_id == "tenant" else ViewingActorType.OPERATOR,
            actor_id=actor_id,
            event_metadata={
                "action": "SLOT_PROPOSED",
                "slot_id": str(slot_record.id),
                "scheduled_start_at": slot_record.start_at.isoformat(),
                "reason": reason or "Candidate slot selected and proposed.",
            },
        )
        self.db.add(event)

        audit = AuditLog(
            action="SLOT_PROPOSED",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={
                "slot_id": str(slot_record.id),
                "scheduled_start_at": slot_record.start_at.isoformat(),
                "scheduled_end_at": slot_record.end_at.isoformat() if slot_record.end_at else None,
                "reason": reason,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(slot_record)
        self.db.refresh(viewing)
        return slot_record

    async def process_inbound_tenant_message(
        self,
        message_id: Optional[uuid.UUID] = None,
        raw_text: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
        override_viewing_id: Optional[uuid.UUID] = None,
        interactive_payload: Optional[Dict[str, Any]] = None,
        actor_id: str = "tenant",
    ) -> TenantAvailabilityUnderstandingResult:
        """
        Full orchestration of tenant scheduling reply:
        1. Fetch message / text.
        2. Correlate to viewing (handles ambiguity safely).
        3. Classify intent.
        4. If cancel -> execute viewing cancellation.
        5. If slot selected or availability provided -> match against active agent slots.
        6. Propose candidate slot if match found.
        7. Audit action.
        """
        # Prompt injection protection check
        text_content = ""
        msg: Optional[WhatsAppMessage] = None
        if message_id:
            msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
            if msg:
                text_content = msg.content or ""
                # Check raw_payload for interactive buttons
                if msg.raw_payload and isinstance(msg.raw_payload, dict):
                    interactive = msg.raw_payload.get("interactive") or {}
                    if interactive:
                        interactive_payload = interactive.get("button_reply") or interactive.get("list_reply")
        if raw_text:
            text_content = raw_text

        text_lower = text_content.lower().strip()
        if "ignore previous instructions" in text_lower or "ignore the slot list" in text_lower:
            logger.warning("Prompt injection pattern detected in tenant scheduling message.")

        # Identify lead
        if not lead_id and msg:
            lead = self.db.query(Lead).filter(Lead.phone_normalized == msg.sender).first()
            if lead:
                lead_id = lead.id

        if not lead_id:
            raise ValueError("Cannot resolve tenant lead for scheduling message.")

        # Correlate Viewing
        viewing, needs_clarification, clar_q = self.correlate_viewing_for_lead(
            lead_id=lead_id,
            message_text=text_content,
            override_viewing_id=override_viewing_id,
            interactive_payload=interactive_payload,
        )

        if needs_clarification or not viewing:
            return TenantAvailabilityUnderstandingResult(
                intent=TenantAvailabilityResponseIntent.UNCLEAR,
                selected_slot_id=None,
                availability_windows=[],
                correlated_viewing_id=None,
                confidence=0.5,
                needs_clarification=True,
                clarification_question=clar_q or "Which property are you referring to?",
                raw_response=text_content,
                metadata={"reason": "Ambiguous viewing correlation across multiple active viewings."},
            )

        # Get active agent slots
        active_agent_slots = self.slot_matching_service.get_active_agent_slots(viewing.id)

        # Classify intent
        intent = self.classify_tenant_intent(
            text=text_content,
            interactive_payload=interactive_payload,
            available_slots=active_agent_slots,
        )

        # Handle Cancellation
        if intent == TenantAvailabilityResponseIntent.CANCEL_VIEWING_REQUEST:
            ViewingService.cancel_viewing(
                db=self.db,
                viewing_id=viewing.id,
                reason="Tenant cancelled viewing via WhatsApp message.",
                cancelled_by="tenant",
            )
            return TenantAvailabilityUnderstandingResult(
                intent=intent,
                selected_slot_id=None,
                availability_windows=[],
                correlated_viewing_id=viewing.id,
                confidence=0.98,
                needs_clarification=False,
                clarification_question=None,
                raw_response=text_content,
                metadata={"status": "VIEWING_CANCELLED"},
            )

        # Handle None of these work
        if intent == TenantAvailabilityResponseIntent.NONE_OF_THESE_WORK:
            if viewing.status == ViewingStatus.SLOTS_AVAILABLE:
                viewing.status = ViewingStatus.AWAITING_TENANT_AVAILABILITY
                self.db.commit()
            return TenantAvailabilityUnderstandingResult(
                intent=intent,
                selected_slot_id=None,
                availability_windows=[],
                correlated_viewing_id=viewing.id,
                confidence=0.95,
                needs_clarification=False,
                clarification_question="What days and times would work better for you?",
                raw_response=text_content,
                metadata={"status": "AWAITING_ALTERNATIVE_AVAILABILITY"},
            )

        # Handle Question about property
        if intent == TenantAvailabilityResponseIntent.ASK_VIEWING_QUESTION:
            prop = viewing.property
            price = getattr(viewing.listing, 'asking_price', None) or 0
            p_name = getattr(prop, 'canonical_name', '') or getattr(prop, 'building_name', '')
            p_addr = getattr(prop, 'address_line_1', '')
            answer = f"The property is {p_name} located at {p_addr}. Rent is ${float(price):,.0f}/month."
            return TenantAvailabilityUnderstandingResult(
                intent=intent,
                selected_slot_id=None,
                availability_windows=[],
                correlated_viewing_id=viewing.id,
                confidence=0.95,
                needs_clarification=False,
                clarification_question=None,
                raw_response=text_content,
                metadata={"answer": answer},
            )

        # Handle Direct Slot Selection
        if intent == TenantAvailabilityResponseIntent.SELECT_SLOT:
            target_slot = None
            if interactive_payload and interactive_payload.get("slot_id"):
                try:
                    s_id = uuid.UUID(str(interactive_payload["slot_id"]))
                    target_slot = self.db.query(ViewingSlot).filter(ViewingSlot.id == s_id).first()
                except Exception:
                    pass

            if not target_slot:
                target_slot = self.resolve_selected_slot_from_text(
                    text=text_content,
                    available_slots=active_agent_slots,
                    viewing_tz=viewing.timezone or "Asia/Singapore",
                )

            if target_slot:
                try:
                    # Match directly and propose
                    proposed_slot = self.propose_candidate_slot(
                        viewing=viewing,
                        candidate_slot=target_slot,
                        actor_id=actor_id,
                        reason="Tenant selected exact agent slot.",
                    )
                    return TenantAvailabilityUnderstandingResult(
                        intent=TenantAvailabilityResponseIntent.SELECT_SLOT,
                        selected_slot_id=proposed_slot.id,
                        availability_windows=[],
                        correlated_viewing_id=viewing.id,
                        confidence=0.98,
                        needs_clarification=False,
                        clarification_question=None,
                        raw_response=text_content,
                        metadata={
                            "match_type": "EXACT",
                            "slot_id": str(proposed_slot.id),
                            "scheduled_start_at": proposed_slot.start_at.isoformat(),
                        },
                    )
                except ValueError as e:
                    # e.g. slot expired
                    return TenantAvailabilityUnderstandingResult(
                        intent=TenantAvailabilityResponseIntent.SELECT_SLOT,
                        selected_slot_id=None,
                        availability_windows=[],
                        correlated_viewing_id=viewing.id,
                        confidence=0.85,
                        needs_clarification=True,
                        clarification_question=f"Sorry, that slot is no longer available ({str(e)}). Please choose another time.",
                        raw_response=text_content,
                        metadata={"error": str(e)},
                    )

        # Handle Provide Availability / Windows
        windows = self.extract_availability_windows(
            text=text_content,
            timezone_str=viewing.timezone or "Asia/Singapore",
        )

        if windows:
            # Store tenant availability windows in viewing_slots
            for w in windows:
                w_start_utc = ViewingSlotMatchingService.to_utc(w.start_at, w.timezone)
                w_end_utc = ViewingSlotMatchingService.to_utc(w.end_at, w.timezone)
                t_slot = ViewingSlot(
                    viewing_id=viewing.id,
                    source=ViewingSlotSource.TENANT,
                    start_at=w_start_utc,
                    end_at=w_end_utc,
                    timezone=w.timezone,
                    status=ViewingSlotStatus.AVAILABLE,
                    source_message_id=msg.id if msg else None,
                )
                self.db.add(t_slot)
            self.db.commit()

            # Run deterministic matching
            match_res: ViewingSlotMatchingResult = self.slot_matching_service.match_slots(
                viewing_id=viewing.id,
                tenant_windows=windows,
            )

            proposed_slot_id = None
            if match_res.recommended_slot:
                try:
                    proposed = self.propose_candidate_slot(
                        viewing=viewing,
                        candidate_slot=match_res.recommended_slot,
                        actor_id=actor_id,
                        reason=match_res.recommended_slot.reason,
                    )
                    proposed_slot_id = proposed.id
                except Exception as e:
                    logger.warning(f"Failed to auto-propose matched slot: {e}")

            return TenantAvailabilityUnderstandingResult(
                intent=TenantAvailabilityResponseIntent.PROVIDE_AVAILABILITY,
                selected_slot_id=proposed_slot_id,
                availability_windows=windows,
                correlated_viewing_id=viewing.id,
                confidence=0.92,
                needs_clarification=(len(match_res.mutual_slots) == 0),
                clarification_question=None if match_res.mutual_slots else "None of the agent's slots overlap with your availability. Could you provide another day/time?",
                raw_response=text_content,
                metadata={
                    "total_mutual_slots": match_res.total_mutual_slots,
                    "status": match_res.status,
                },
            )

        # If unclear
        return TenantAvailabilityUnderstandingResult(
            intent=intent,
            selected_slot_id=None,
            availability_windows=[],
            correlated_viewing_id=viewing.id,
            confidence=0.6,
            needs_clarification=True,
            clarification_question="Could you please specify a preferred date and time for the viewing?",
            raw_response=text_content,
            metadata={},
        )
