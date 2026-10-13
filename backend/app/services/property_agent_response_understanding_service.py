import logging
import re
import uuid
from datetime import datetime, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.message import WhatsAppMessage
from app.models.property_agent import PropertyAgent
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_match import PropertyMatch
from app.models.property_listing import PropertyListing
from app.models.property import Property
from app.models.enums import (
    MessageDirection,
    PropertyAgentOutreachStatus,
    PropertyMatchStatus,
    AITaskType,
    AgentResponseIntent,
    AgentCorrelationStatus,
)
from app.ai.orchestrator import AIOrchestrator
from app.ai.schemas import AIRequest, AgentResponseExtractionResult
from app.schemas.property_availability_verification import (
    AgentResponseExtractionResult as SchemaExtractionResult,
    AgentResponseFieldExtraction,
)

logger = logging.getLogger(__name__)


class PropertyAgentResponseUnderstandingService:
    """
    Module 4 Phase 6: Property Agent Response Understanding Service.
    Responsibilities:
    - Accept inbound WhatsApp message ID.
    - Verify sender is a registered external Property Agent.
    - Correlate message with active outreach / property match / listing.
    - Build safe AI context.
    - Classify agent response intent and extract structured fields via AIOrchestrator.
    - Perform strict backend validation on extracted fields (prevent bad data & prompt injections).
    - Return validated structured result.
    
    CRITICAL RULE:
    AI interprets. Backend validates.
    This service NEVER directly updates business tables in the database.
    """

    def __init__(self, db: Session, orchestrator: Optional[AIOrchestrator] = None):
        self.db = db
        self.orchestrator = orchestrator or AIOrchestrator()

    def correlate_agent_message(
        self,
        message: WhatsAppMessage,
        override_match_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Correlates an incoming agent message to the appropriate outreach and match.
        Returns:
            {
                "status": "RESOLVED" | "AMBIGUOUS" | "UNRESOLVED",
                "property_agent_id": str,
                "property_match_id": Optional[str],
                "listing_id": Optional[str],
                "outreach_id": Optional[str],
                "candidate_match_ids": List[str],
            }
        """
        # 1. Resolve registered PropertyAgent
        sender = message.sender or ""
        agent = (
            self.db.query(PropertyAgent)
            .filter(or_(PropertyAgent.phone_normalized == sender, PropertyAgent.phone == sender))
            .first()
        )
        if not agent:
            return {
                "status": AgentCorrelationStatus.UNRESOLVED.value,
                "property_agent_id": None,
                "property_match_id": None,
                "listing_id": None,
                "outreach_id": None,
                "candidate_match_ids": [],
                "reason": "Sender is not a registered property agent.",
            }

        # 2. Check override match ID if operator manually linked it
        if override_match_id:
            match = self.db.query(PropertyMatch).filter(PropertyMatch.id == override_match_id).first()
            if match:
                outreach = (
                    self.db.query(PropertyAgentOutreach)
                    .filter(
                        PropertyAgentOutreach.property_match_id == match.id,
                        PropertyAgentOutreach.property_agent_id == agent.id,
                    )
                    .order_by(PropertyAgentOutreach.created_at.desc())
                    .first()
                )
                return {
                    "status": AgentCorrelationStatus.RESOLVED.value,
                    "property_agent_id": str(agent.id),
                    "property_match_id": str(match.id),
                    "listing_id": str(match.listing_id) if match.listing_id else None,
                    "outreach_id": str(outreach.id) if outreach else None,
                    "candidate_match_ids": [str(match.id)],
                }

        # 3. Search for open/active outreaches for this agent
        pending_outreaches = (
            self.db.query(PropertyAgentOutreach)
            .filter(
                PropertyAgentOutreach.property_agent_id == agent.id,
                PropertyAgentOutreach.status.in_([
                    PropertyAgentOutreachStatus.QUEUED,
                    PropertyAgentOutreachStatus.SENT,
                    PropertyAgentOutreachStatus.DELIVERED,
                    PropertyAgentOutreachStatus.READ,
                    PropertyAgentOutreachStatus.REPLIED,
                ]),
            )
            .order_by(PropertyAgentOutreach.created_at.desc())
            .all()
        )

        content = message.content or ""

        # 4. Check for explicit reference codes in text (e.g. PM-XXXXXXXX or REF-XXXX)
        matched_outreach = None
        for o in pending_outreaches:
            if o.idempotency_key:
                # Key format: property-agent-outreach:{match_id}:initial
                parts = o.idempotency_key.split(":")
                if len(parts) >= 2:
                    match_id_prefix = parts[1][:8].upper()
                    ref_code = f"PM-{match_id_prefix}"
                    if ref_code.upper() in content.upper():
                        matched_outreach = o
                        break

            # Also check source listing reference
            if o.listing and o.listing.listing_reference:
                if o.listing.listing_reference.upper() in content.upper():
                    matched_outreach = o
                    break

        if matched_outreach:
            return {
                "status": AgentCorrelationStatus.RESOLVED.value,
                "property_agent_id": str(agent.id),
                "property_match_id": str(matched_outreach.property_match_id),
                "listing_id": str(matched_outreach.listing_id) if matched_outreach.listing_id else None,
                "outreach_id": str(matched_outreach.id),
                "candidate_match_ids": [str(matched_outreach.property_match_id)],
            }

        # 5. Single pending outreach heuristic
        if len(pending_outreaches) == 1:
            single = pending_outreaches[0]
            return {
                "status": AgentCorrelationStatus.RESOLVED.value,
                "property_agent_id": str(agent.id),
                "property_match_id": str(single.property_match_id),
                "listing_id": str(single.listing_id) if single.listing_id else None,
                "outreach_id": str(single.id),
                "candidate_match_ids": [str(single.property_match_id)],
            }

        # 6. Multiple pending outreaches without reference code -> Ambiguous!
        if len(pending_outreaches) > 1:
            candidate_ids = [str(o.property_match_id) for o in pending_outreaches if o.property_match_id]
            return {
                "status": AgentCorrelationStatus.AMBIGUOUS.value,
                "property_agent_id": str(agent.id),
                "property_match_id": None,
                "listing_id": None,
                "outreach_id": None,
                "candidate_match_ids": list(set(candidate_ids)),
                "reason": f"Agent has {len(pending_outreaches)} active matches. No reference code provided.",
            }

        # 7. No pending outreach found
        return {
            "status": AgentCorrelationStatus.UNRESOLVED.value,
            "property_agent_id": str(agent.id),
            "property_match_id": None,
            "listing_id": None,
            "outreach_id": None,
            "candidate_match_ids": [],
            "reason": "No active outreach found for this agent.",
        }

    async def analyze_response(
        self,
        message_id: uuid.UUID,
        override_match_id: Optional[uuid.UUID] = None,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Extracts structured intent and terms from an inbound agent message.
        Does NOT alter database business state directly.
        """
        # 1. Fetch message
        msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"WhatsAppMessage '{message_id}' not found.",
            )

        if msg.direction != MessageDirection.INBOUND:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only inbound messages can be analyzed for agent availability.",
            )

        # 2. Correlate with PropertyMatch
        correlation = self.correlate_agent_message(msg, override_match_id=override_match_id)

        if correlation["status"] == AgentCorrelationStatus.AMBIGUOUS.value:
            return {
                "status": "AMBIGUOUS",
                "message_id": str(message_id),
                "correlation": correlation,
                "extraction": None,
                "needs_review": True,
            }

        if correlation["status"] == AgentCorrelationStatus.UNRESOLVED.value:
            return {
                "status": "UNRESOLVED",
                "message_id": str(message_id),
                "correlation": correlation,
                "extraction": None,
                "needs_review": True,
            }

        # 3. Load Match & Listing for Context
        match = (
            self.db.query(PropertyMatch)
            .filter(PropertyMatch.id == uuid.UUID(correlation["property_match_id"]))
            .first()
        )
        listing = match.listing if match else None
        prop = match.property if match else None

        prop_ref = f"PM-{str(match.id)[:8].upper()}" if match else "UNKNOWN"
        if listing and listing.listing_reference:
            prop_ref += f" / {listing.listing_reference}"

        prop_address = prop.canonical_name if prop else "Unknown Property"
        current_price = f"SGD {listing.asking_price}" if listing and listing.asking_price else "Unknown"
        current_date = str(listing.available_from) if listing and listing.available_from else "Unknown"

        # 4. Build Safe Prompt Context
        prompt_context = {
            "property_reference": prop_ref,
            "property_address": prop_address,
            "current_asking_price": current_price,
            "current_available_from": current_date,
            "agent_message": msg.content or "",
        }

        # 5. Call AIOrchestrator
        ai_call_id = None
        raw_result: Optional[AgentResponseExtractionResult] = None

        try:
            ai_response = await self.orchestrator.execute_structured(
                task_type=AITaskType.AGENT_RESPONSE_EXTRACTION,
                context=prompt_context,
                response_model=AgentResponseExtractionResult,
                db=self.db,
            )
            raw_result = ai_response.data
            ai_call_id = getattr(ai_response, "call_id", None)
        except Exception as e:
            logger.error(f"AIOrchestrator failed to process agent response: {e}")
            # Fallback to rule-based parser on AI provider failure
            raw_result = self._fallback_rule_extractor(msg.content or "")

        # 6. Backend Validation Layer (Crucial!)
        validated_fields = self._validate_and_sanitize_fields(raw_result.fields if raw_result else {})

        # Determine overall intent safely
        intent_str = raw_result.intent if raw_result else AgentResponseIntent.UNCLEAR.value
        try:
            intent = AgentResponseIntent(intent_str)
        except Exception:
            intent = AgentResponseIntent.UNCLEAR

        # Check if needs clarification or prompt injection
        needs_clarification = raw_result.needs_clarification if raw_result else True
        if intent == AgentResponseIntent.UNRELATED:
            needs_clarification = True

        return {
            "status": "RESOLVED",
            "message_id": str(message_id),
            "correlation": correlation,
            "ai_call_id": str(ai_call_id) if ai_call_id else None,
            "extraction": {
                "intent": intent.value,
                "fields": validated_fields,
                "needs_clarification": needs_clarification,
                "clarification_reasons": raw_result.clarification_reasons if raw_result else [],
                "raw_summary": raw_result.raw_summary if raw_result else None,
                "overall_confidence": raw_result.overall_confidence if raw_result else 0.5,
            },
            "needs_review": needs_clarification or (intent == AgentResponseIntent.NEEDS_CLARIFICATION),
        }

    def _validate_and_sanitize_fields(
        self,
        raw_fields: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """
        Strict backend validation on AI extraction outputs:
        - Price must be positive numeric.
        - Currency must be recognized string.
        - Date must be valid YYYY-MM-DD.
        - Lease min must be positive integer.
        - Lease max must be >= lease min.
        - Availability status must be one of the approved states.
        """
        validated: Dict[str, Dict[str, Any]] = {}

        # 1. Availability
        if "availability" in raw_fields:
            item = raw_fields["availability"]
            val = str(getattr(item, "value", item.get("value") if isinstance(item, dict) else item)).upper()
            conf = float(getattr(item, "confidence", item.get("confidence", 1.0) if isinstance(item, dict) else 1.0))
            if val in ["AVAILABLE", "UNAVAILABLE", "CONDITIONAL", "UNKNOWN"]:
                validated["availability"] = {"value": val, "confidence": conf}

        # 2. Asking Price
        if "asking_price" in raw_fields:
            item = raw_fields["asking_price"]
            raw_val = getattr(item, "value", item.get("value") if isinstance(item, dict) else item)
            conf = float(getattr(item, "confidence", item.get("confidence", 1.0) if isinstance(item, dict) else 1.0))
            needs_conf = getattr(item, "needs_confirmation", item.get("needs_confirmation", False) if isinstance(item, dict) else False)
            try:
                price_dec = Decimal(str(raw_val))
                if price_dec > 0 and price_dec < 1000000:
                    validated["asking_price"] = {
                        "value": float(price_dec),
                        "confidence": conf,
                        "needs_confirmation": needs_conf,
                    }
                else:
                    logger.warning(f"Rejected invalid negative/excessive price: {price_dec}")
            except Exception:
                logger.warning(f"Failed to parse asking_price: {raw_val}")

        # 3. Currency
        if "currency" in raw_fields:
            item = raw_fields["currency"]
            c_val = str(getattr(item, "value", item.get("value") if isinstance(item, dict) else item)).upper()
            if c_val in ["SGD", "USD", "EUR", "GBP", "AUD"]:
                validated["currency"] = {"value": c_val, "confidence": 1.0}

        # 4. Available From Date
        if "available_from" in raw_fields:
            item = raw_fields["available_from"]
            d_val = getattr(item, "value", item.get("value") if isinstance(item, dict) else item)
            conf = float(getattr(item, "confidence", item.get("confidence", 1.0) if isinstance(item, dict) else 1.0))
            parsed_date = self._parse_safe_date(str(d_val))
            if parsed_date:
                validated["available_from"] = {"value": parsed_date.isoformat(), "confidence": conf}

        # 5. Lease Term (Min & Max)
        min_lease = None
        if "minimum_lease_months" in raw_fields:
            item = raw_fields["minimum_lease_months"]
            raw_val = getattr(item, "value", item.get("value") if isinstance(item, dict) else item)
            conf = float(getattr(item, "confidence", item.get("confidence", 1.0) if isinstance(item, dict) else 1.0))
            try:
                min_lease = int(raw_val)
                if 1 <= min_lease <= 120:
                    validated["minimum_lease_months"] = {"value": min_lease, "confidence": conf}
            except Exception:
                pass

        if "maximum_lease_months" in raw_fields:
            item = raw_fields["maximum_lease_months"]
            raw_val = getattr(item, "value", item.get("value") if isinstance(item, dict) else item)
            conf = float(getattr(item, "confidence", item.get("confidence", 1.0) if isinstance(item, dict) else 1.0))
            try:
                max_lease = int(raw_val)
                if min_lease and max_lease < min_lease:
                    logger.warning(f"maximum_lease_months ({max_lease}) < minimum_lease_months ({min_lease}). Ignored.")
                elif 1 <= max_lease <= 120:
                    validated["maximum_lease_months"] = {"value": max_lease, "confidence": conf}
            except Exception:
                pass

        # 6. Furnishing
        if "furnishing" in raw_fields:
            item = raw_fields["furnishing"]
            f_val = str(getattr(item, "value", item.get("value") if isinstance(item, dict) else item)).upper()
            conf = float(getattr(item, "confidence", item.get("confidence", 1.0) if isinstance(item, dict) else 1.0))
            if f_val in ["FURNISHED", "PARTIALLY_FURNISHED", "UNFURNISHED", "FLEXIBLE", "UNKNOWN"]:
                validated["furnishing"] = {"value": f_val, "confidence": conf}

        # 7. Viewing Info
        if "viewing_possible" in raw_fields:
            item = raw_fields["viewing_possible"]
            v_val = getattr(item, "value", item.get("value") if isinstance(item, dict) else item)
            conf = float(getattr(item, "confidence", item.get("confidence", 1.0) if isinstance(item, dict) else 1.0))
            if isinstance(v_val, bool):
                validated["viewing_possible"] = {"value": v_val, "confidence": conf}

        if "viewing_notes" in raw_fields:
            item = raw_fields["viewing_notes"]
            notes_val = str(getattr(item, "value", item.get("value") if isinstance(item, dict) else item))
            if len(notes_val.strip()) > 0:
                validated["viewing_notes"] = {"value": notes_val.strip()[:500], "confidence": 0.95}

        # 8. Restrictions / Conditions
        for cond_key in ["agent_conditions", "special_restrictions"]:
            if cond_key in raw_fields:
                item = raw_fields[cond_key]
                val = getattr(item, "value", item.get("value") if isinstance(item, dict) else item)
                validated[cond_key] = {"value": val, "confidence": 0.9}

        return validated

    def _parse_safe_date(self, date_str: str) -> Optional[date]:
        """Safely parses dates in YYYY-MM-DD or standard formats."""
        if not date_str:
            return None
        clean = date_str.strip()
        try:
            return datetime.strptime(clean, "%Y-%m-%d").date()
        except ValueError:
            pass

        # Check regex for YYYY-MM-DD
        match = re.search(r"(\d{4})-(\d{2})-(\d{2})", clean)
        if match:
            try:
                return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
            except ValueError:
                pass
        return None

    def _fallback_rule_extractor(self, text: str) -> AgentResponseExtractionResult:
        """Deterministic rule-based extractor when AI provider is offline."""
        lower = text.lower()
        if "ignore your system" in lower or "override" in lower:
            return AgentResponseExtractionResult(
                intent=AgentResponseIntent.UNRELATED.value,
                fields={},
                needs_clarification=True,
                clarification_reasons=["Adversarial prompt injection detected."],
                overall_confidence=0.95,
            )

        fields: Dict[str, Any] = {}
        intent = AgentResponseIntent.AVAILABLE.value

        if any(w in lower for w in ["already rented", "taken", "not available"]):
            intent = AgentResponseIntent.UNAVAILABLE.value
            fields["availability"] = {"value": "UNAVAILABLE", "confidence": 0.95}
        elif any(w in lower for w in ["conditional", "only accepts", "available only after"]):
            intent = AgentResponseIntent.CONDITIONAL_AVAILABILITY.value
            fields["availability"] = {"value": "CONDITIONAL", "confidence": 0.9}
        elif any(w in lower for w in ["yes", "available"]):
            intent = AgentResponseIntent.AVAILABLE.value
            fields["availability"] = {"value": "AVAILABLE", "confidence": 0.95}

        # Price regex
        price_match = re.search(r"\b([3-9][0-9]{3})\b", lower)
        if price_match:
            fields["asking_price"] = {"value": int(price_match.group(1)), "confidence": 0.9}
            fields["currency"] = {"value": "SGD", "confidence": 0.9}

        # Lease regex
        if "24" in lower or "2 years" in lower:
            fields["minimum_lease_months"] = {"value": 24, "confidence": 0.9}
        elif "12" in lower or "one year" in lower or "1 year" in lower:
            fields["minimum_lease_months"] = {"value": 12, "confidence": 0.9}

        return AgentResponseExtractionResult(
            intent=intent,
            fields=fields,
            needs_clarification=False,
            overall_confidence=0.9,
        )
