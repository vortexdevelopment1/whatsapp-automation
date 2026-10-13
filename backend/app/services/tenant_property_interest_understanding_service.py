"""
Tenant Property Interest Understanding Service - Module 5 Phase 2
Correlates inbound tenant WhatsApp messages or interactive clicks to presented properties,
classifies tenant interest intents, answers structured property questions,
and safely transitions property interests into Module 5 viewing workflows.
"""
import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.enums import (
    PropertyInterestStatus,
    TenantInterestIntent,
    ViewingStatus,
)
from app.models.lead import Lead
from app.models.property_match import PropertyMatch
from app.models.property_interest import PropertyInterest
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
from app.models.audit_log import AuditLog
from app.schemas.property_interest import (
    TenantInterestProcessResult,
    PropertyInterestResponse,
)
from app.services.viewing_service import ViewingService
from app.services.tenant_property_presentation_service import TenantPropertyPresentationService

logger = logging.getLogger(__name__)


class TenantPropertyInterestUnderstandingService:
    """
    Authoritative service governing tenant interest classification and property correlation.
    Strict safety rules:
    - AI / NLP never directly mutates viewing states; backend workflow owns status.
    - Grounded Q&A only from structured DB fields (no hallucinated amenities).
    - Viewing workflow triggered ONLY upon unambiguous REQUEST_VIEWING intent.
    - Protects against duplicate viewing creation.
    """

    VIEWING_KEYWORDS = [
        "view", "viewing", "visit", "see it in person", "arrange viewing",
        "schedule viewing", "book viewing", "take a look", "check it out", "want to see"
    ]
    INTERESTED_KEYWORDS = [
        "like this", "love this", "looks good", "interested in this",
        "nice place", "looks nice", "great option", "sounds good", "like it"
    ]
    NOT_INTERESTED_KEYWORDS = [
        "not interested", "skip this", "too expensive", "don't like",
        "do not like", "pass on this", "no thanks", "no, skip", "next please"
    ]
    MORE_DETAILS_KEYWORDS = [
        "more details", "tell me more", "photos", "pictures", "send link",
        "brochure", "more info", "information"
    ]
    NEXT_OPTION_KEYWORDS = [
        "show me another", "next property", "next one", "what else",
        "another option", "show next"
    ]
    OTHER_OPTIONS_KEYWORDS = [
        "cheaper options", "different location", "other properties",
        "more options", "something cheaper"
    ]

    @classmethod
    def correlate_property(
        cls,
        db: Session,
        lead_id: uuid.UUID,
        message_text: str,
        interactive_payload: Optional[str] = None,
    ) -> Tuple[Optional[PropertyMatch], Optional[PropertyInterest], bool, Optional[str]]:
        """
        Determines which property match the tenant is referring to.
        Returns: (match, interest, needs_clarification, clarification_question)
        """
        # 1. Structured interactive payload correlation (Highest precedence)
        if interactive_payload:
            parts = interactive_payload.split(":")
            if len(parts) >= 2:
                try:
                    match_id = uuid.UUID(parts[1])
                    match = db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
                    if match and match.lead_id == lead_id:
                        interest = (
                            db.query(PropertyInterest)
                            .filter(
                                PropertyInterest.lead_id == lead_id,
                                PropertyInterest.property_match_id == match_id,
                            )
                            .first()
                        )
                        return match, interest, False, None
                except ValueError:
                    pass

        # 2. Load all presented properties for this lead ordered by presented_at descending
        presented_interests = (
            db.query(PropertyInterest)
            .filter(
                PropertyInterest.lead_id == lead_id,
                PropertyInterest.status != PropertyInterestStatus.NOT_PRESENTED,
            )
            .order_by(PropertyInterest.presented_at.desc())
            .all()
        )

        if not presented_interests:
            return None, None, False, None

        text_lower = message_text.lower().strip()

        # 3. Explicit Name / Building / District match
        for pi in presented_interests:
            match = pi.property_match
            if not match:
                continue
            prop: Optional[Property] = match.property
            if not prop:
                continue

            # Check canonical name, building name, or district
            if prop.canonical_name and prop.canonical_name.lower() in text_lower:
                return match, pi, False, None
            if prop.building_name and prop.building_name.lower() in text_lower:
                return match, pi, False, None
            if prop.district and prop.district.lower() in text_lower:
                return match, pi, False, None

        # 4. Ordinal references ("first one", "second one", "option 1", "property 2")
        shortlist = (
            db.query(PropertyShortlist)
            .filter(PropertyShortlist.lead_id == lead_id)
            .order_by(PropertyShortlist.version.desc())
            .first()
        )
        if shortlist and shortlist.items:
            items_by_pos = {it.position: it for it in shortlist.items}
            ord_map = {
                "first": 1, "1st": 1, "option 1": 1, "#1": 1, "property 1": 1,
                "second": 2, "2nd": 2, "option 2": 2, "#2": 2, "property 2": 2,
                "third": 3, "3rd": 3, "option 3": 3, "#3": 3, "property 3": 3,
            }
            for term, pos in ord_map.items():
                if term in text_lower and pos in items_by_pos:
                    item = items_by_pos[pos]
                    pi = next((p for p in presented_interests if p.property_match_id == item.property_match_id), None)
                    return item.property_match, pi, False, None

        # 5. Single presented property heuristic
        if len(presented_interests) == 1:
            return presented_interests[0].property_match, presented_interests[0], False, None

        # 6. Pronoun references ("this one", "it", "that one") with multiple presented properties
        ambiguous_pronouns = ["that one", "which one", "the place", "that property"]
        if any(p in text_lower for p in ambiguous_pronouns):
            names = []
            for pi in presented_interests[:2]:
                if pi.property_match and pi.property_match.property:
                    names.append(pi.property_match.property.canonical_name or "Shortlisted Property")
            names_str = " or ".join(names) if names else "the properties"
            return None, None, True, f"Could you clarify which property you mean? (e.g. {names_str})"

        # Default to most recently presented property
        most_recent = presented_interests[0]
        return most_recent.property_match, most_recent, False, None

    @classmethod
    def classify_intent(
        cls,
        message_text: str,
        interactive_payload: Optional[str] = None,
    ) -> TenantInterestIntent:
        """
        Classifies tenant message intent deterministically.
        """
        # Interactive payload takes precedence
        if interactive_payload:
            action = interactive_payload.split(":")[0]
            if action in ("view_property", "request_viewing"):
                return TenantInterestIntent.REQUEST_VIEWING
            elif action in ("more_details", "details"):
                return TenantInterestIntent.REQUEST_MORE_DETAILS
            elif action in ("not_interested", "skip"):
                return TenantInterestIntent.NOT_INTERESTED
            elif action in ("next_property", "next"):
                return TenantInterestIntent.REQUEST_NEXT_OPTION

        text = message_text.lower().strip()

        # Check viewing keywords first (even if phrased as a question like "Can I view?")
        if any(kw in text for kw in cls.VIEWING_KEYWORDS):
            return TenantInterestIntent.REQUEST_VIEWING

        # Check more details keywords (even if phrased as a question like "Can you share more details?")
        if any(kw in text for kw in cls.MORE_DETAILS_KEYWORDS):
            return TenantInterestIntent.REQUEST_MORE_DETAILS

        # Check next option
        if any(kw in text for kw in cls.NEXT_OPTION_KEYWORDS):
            return TenantInterestIntent.REQUEST_NEXT_OPTION

        # Check other options
        if any(kw in text for kw in cls.OTHER_OPTIONS_KEYWORDS):
            return TenantInterestIntent.REQUEST_OTHER_OPTIONS

        # Check negative interest
        if any(kw in text for kw in cls.NOT_INTERESTED_KEYWORDS):
            return TenantInterestIntent.NOT_INTERESTED

        # Check comparison
        if "which is" in text or "compare" in text:
            return TenantInterestIntent.COMPARE_PROPERTIES

        # Check Q&A questions
        question_words = ["is it", "does it", "how much", "when is", "how many", "any ", "what is", "parking", "furnished", "rent"]
        if any(qw in text for qw in question_words) or "?" in text:
            return TenantInterestIntent.ASK_PROPERTY_QUESTION

        # Check positive interest
        if any(kw in text for kw in cls.INTERESTED_KEYWORDS):
            return TenantInterestIntent.INTERESTED

        # Single word replies
        if text in ("yes", "yep", "interested", "ok"):
            return TenantInterestIntent.INTERESTED
        if text in ("no", "nope", "skip", "pass"):
            return TenantInterestIntent.NOT_INTERESTED

        return TenantInterestIntent.UNCLEAR

    @classmethod
    def answer_property_question(
        cls,
        match: PropertyMatch,
        question_text: str,
    ) -> str:
        """
        Grounded property Q&A strictly from structured database fields.
        Does NOT hallucinate unconfirmed amenities.
        """
        prop: Optional[Property] = match.property
        listing: Optional[PropertyListing] = match.listing
        q = question_text.lower()

        answers = []
        name = prop.canonical_name if prop else "This property"

        if "furnish" in q:
            furn = (
                prop.furnishing.value.replace("_", " ").title()
                if prop and prop.furnishing
                else "Unspecified"
            )
            answers.append(f"{name} is {furn}.")

        if "rent" in q or "price" in q or "cost" in q or "how much" in q:
            price = listing.asking_price if listing and listing.asking_price is not None else None
            curr = listing.currency if listing else "SGD"
            if price:
                answers.append(f"The asking rent is {curr} {price:,.0f}/month.")
            else:
                answers.append("The rent is available upon inquiry.")

        if "when" in q or "available" in q or "move in" in q:
            avail = str(listing.available_from) if listing and listing.available_from else None
            if avail:
                answers.append(f"It is available from {avail}.")
            else:
                answers.append(f"Availability is currently listed as {listing.availability_status.value if listing else 'Immediate'}.")

        if "bedroom" in q or "bed" in q:
            beds = prop.bedrooms if prop else None
            answers.append(f"It has {beds} bedrooms." if beds else "Bedroom count is not specified.")

        if "bathroom" in q or "bath" in q:
            baths = prop.bathrooms if prop else None
            answers.append(f"It has {baths} bathrooms." if baths else "Bathroom count is not specified.")

        if "size" in q or "sqft" in q:
            sqft = prop.size_sqft if prop else None
            answers.append(f"The size is {sqft:,.0f} sqft." if sqft else "Size details are not currently recorded.")

        # Check unknown amenities (parking, gym, pool, balcony, pets)
        unknown_amenities = ["parking", "car park", "gym", "pool", "balcony", "pet"]
        for ua in unknown_amenities:
            if ua in q:
                answers.append(
                    f"Information regarding {ua} is not currently confirmed in our database. We can verify this with the listing agent for you!"
                )

        if not answers:
            # General fallback factual answer
            answers.append(
                f"{name} is a {prop.bedrooms or ''}-bedroom {prop.property_type.value if prop else 'property'} "
                f"at {prop.address_normalized or prop.district or 'Singapore'}."
            )

        return " ".join(answers)

    @classmethod
    def compare_presented_properties(
        cls,
        db: Session,
        lead_id: uuid.UUID,
    ) -> str:
        """
        Factual deterministic property comparison without exposing internal match scores.
        """
        interests = (
            db.query(PropertyInterest)
            .filter(
                PropertyInterest.lead_id == lead_id,
                PropertyInterest.status != PropertyInterestStatus.NOT_PRESENTED,
            )
            .order_by(PropertyInterest.presented_at.asc())
            .limit(3)
            .all()
        )

        if len(interests) < 2:
            return "Only one property has been presented so far. Would you like me to show you another option to compare?"

        lines = ["Here is a quick factual comparison of your shortlisted options:\n"]
        for idx, pi in enumerate(interests, start=1):
            m = pi.property_match
            p = m.property if m else None
            l = m.listing if m else None
            name = p.canonical_name if p else f"Property #{idx}"
            price = f"${l.asking_price:,.0f}/mo" if l and l.asking_price else "Price upon inquiry"
            beds = f"{p.bedrooms} Beds" if p and p.bedrooms else "—"
            furn = p.furnishing.value.replace("_", " ").title() if p and p.furnishing else "—"
            avail = str(l.available_from) if l and l.available_from else "Immediate"
            lines.append(f"• *{name}*: {price} · {beds} · {furn} · Available: {avail}")

        lines.append("\nWhich of these would you prefer to view?")
        return "\n".join(lines)

    @classmethod
    def process_tenant_response(
        cls,
        db: Session,
        lead_id: uuid.UUID,
        message_content: str,
        interactive_payload: Optional[str] = None,
        inbound_message_id: Optional[uuid.UUID] = None,
        actor_id: str = "tenant",
    ) -> TenantInterestProcessResult:
        """
        Main orchestrator handling inbound tenant feedback on presented properties.
        Validates property correlation, classifies intent, updates interest state,
        answers grounded questions, and creates a viewing record if requested.
        """
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        # 1. Correlate referenced property
        match, interest, needs_clarification, clar_q = cls.correlate_property(
            db=db,
            lead_id=lead_id,
            message_text=message_content,
            interactive_payload=interactive_payload,
        )

        if needs_clarification:
            return TenantInterestProcessResult(
                intent=TenantInterestIntent.UNCLEAR,
                needs_clarification=True,
                clarification_question=clar_q,
                response_text=clar_q,
            )

        # 2. Classify intent
        intent = cls.classify_intent(
            message_text=message_content,
            interactive_payload=interactive_payload,
        )

        # 3. Handle Property Comparison
        if intent == TenantInterestIntent.COMPARE_PROPERTIES:
            comp_text = cls.compare_presented_properties(db, lead_id)
            return TenantInterestProcessResult(
                intent=TenantInterestIntent.COMPARE_PROPERTIES,
                response_text=comp_text,
            )

        # 4. Handle Request for Next Property
        if intent == TenantInterestIntent.REQUEST_NEXT_OPTION:
            try:
                pres_res = TenantPropertyPresentationService.present_shortlist(
                    db=db,
                    lead_id=lead_id,
                    actor_id=actor_id,
                )
                prop_name = (
                    pres_res.items[0].property_summary.name
                    if pres_res.items and pres_res.items[0].property_summary
                    else "the next property"
                )
                return TenantInterestProcessResult(
                    intent=TenantInterestIntent.REQUEST_NEXT_OPTION,
                    response_text=f"Here is another option for you: {prop_name}",
                    property_interest=pres_res.items[0] if pres_res.items else None,
                )
            except Exception as e:
                return TenantInterestProcessResult(
                    intent=TenantInterestIntent.REQUEST_NEXT_OPTION,
                    response_text="You have seen all properties in your current shortlist. Would you like me to refine your search criteria?",
                )

        # If no property could be correlated and not a comparison/next option
        if not match:
            return TenantInterestProcessResult(
                intent=intent,
                needs_clarification=False,
                response_text="Thank you for your message! Would you like to view our latest shortlisted properties?",
            )

        # 5. Revalidation: ensure candidate is still active and available
        if match.is_stale or match.availability_status == "UNAVAILABLE":
            return TenantInterestProcessResult(
                intent=intent,
                correlated_property_match_id=match.id,
                response_text=(
                    f"We apologize, but {match.property.canonical_name if match.property else 'this property'} "
                    "is no longer available. Would you like to see another option from your shortlist?"
                ),
            )

        # If interest record does not exist yet (e.g. correlated before formal presentation record), create one
        if not interest:
            interest = PropertyInterest(
                lead_id=lead.id,
                property_match_id=match.id,
                status=PropertyInterestStatus.PRESENTED,
                presented_at=datetime.now(timezone.utc),
            )
            db.add(interest)
            db.commit()
            db.refresh(interest)

        now = datetime.now(timezone.utc)
        viewing_created = False
        viewing_id = None
        response_text = ""

        # 6. Execute domain actions according to intent
        if intent == TenantInterestIntent.REQUEST_VIEWING:
            interest.status = PropertyInterestStatus.VIEWING_REQUESTED
            interest.last_intent = TenantInterestIntent.REQUEST_VIEWING
            interest.responded_at = now
            interest.tenant_notes = message_content

            # Create or reuse Module 5 viewing record via ViewingService
            viewing = ViewingService.create_viewing_from_match(
                db=db,
                match_id=match.id,
                created_by="tenant",
            )
            interest.viewing_id = viewing.id
            viewing_created = True
            viewing_id = viewing.id

            prop_name = match.property.canonical_name if match.property else "this property"
            response_text = (
                f"Awesome! I've recorded your viewing request for *{prop_name}*. "
                "Our team will now coordinate available viewing slots with the listing agent and get back to you shortly."
            )

        elif intent == TenantInterestIntent.INTERESTED:
            interest.status = PropertyInterestStatus.INTERESTED
            interest.last_intent = TenantInterestIntent.INTERESTED
            interest.responded_at = now
            interest.tenant_notes = message_content

            prop_name = match.property.canonical_name if match.property else "this property"
            response_text = (
                f"Glad to hear you like *{prop_name}*! "
                "Would you like me to arrange an in-person or virtual viewing for you?"
            )

        elif intent == TenantInterestIntent.NOT_INTERESTED:
            interest.status = PropertyInterestStatus.NOT_INTERESTED
            interest.last_intent = TenantInterestIntent.NOT_INTERESTED
            interest.responded_at = now
            interest.tenant_notes = message_content

            response_text = (
                "Got it, I've noted that this property isn't the right fit. "
                "Would you like me to show you the next option from your shortlist?"
            )

        elif intent == TenantInterestIntent.REQUEST_MORE_DETAILS:
            interest.status = PropertyInterestStatus.WANTS_MORE_DETAILS
            interest.last_intent = TenantInterestIntent.REQUEST_MORE_DETAILS
            interest.responded_at = now

            summary = TenantPropertyPresentationService.format_tenant_safe_summary(match)
            response_text = f"Here are the complete details for {summary.name}:\n\n{summary.summary_text}"

        elif intent == TenantInterestIntent.ASK_PROPERTY_QUESTION:
            interest.last_intent = TenantInterestIntent.ASK_PROPERTY_QUESTION
            interest.responded_at = now
            response_text = cls.answer_property_question(match, message_content)

        elif intent == TenantInterestIntent.REQUEST_OTHER_OPTIONS:
            interest.status = PropertyInterestStatus.OTHER_OPTIONS_REQUESTED
            interest.last_intent = TenantInterestIntent.REQUEST_OTHER_OPTIONS
            interest.responded_at = now
            response_text = "I've noted that you'd like to explore other options. Let me check for additional matching properties."

        else:
            response_text = "Thank you for your reply! Let me know if you would like to schedule a viewing or see more details."

        db.commit()
        db.refresh(interest)

        # 7. Audit log
        audit = AuditLog(
            actor_id=actor_id,
            action="TENANT_PROPERTY_INTEREST_CAPTURED",
            entity_type="PropertyInterest",
            entity_id=str(interest.id),
            new_value={
                "intent": intent.value,
                "viewing_created": viewing_created,
                "viewing_id": str(viewing_id) if viewing_id else None,
                "message": message_content,
            },
        )
        db.add(audit)
        db.commit()

        resp_obj = PropertyInterestResponse.model_validate(interest)
        if interest.property_match:
            resp_obj.property_summary = TenantPropertyPresentationService.format_tenant_safe_summary(
                interest.property_match
            )

        return TenantInterestProcessResult(
            intent=intent,
            correlated_property_match_id=match.id,
            confidence=1.0,
            needs_clarification=False,
            viewing_created=viewing_created,
            viewing_id=viewing_id,
            response_text=response_text,
            property_interest=resp_obj,
        )
