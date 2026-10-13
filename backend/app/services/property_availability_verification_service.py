import logging
import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_source import PropertySource
from app.models.property_match import PropertyMatch
from app.models.property_agent import PropertyAgent
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_availability_verification import PropertyAvailabilityVerification
from app.models.message import WhatsAppMessage
from app.models.enums import (
    PropertyMatchStatus,
    PropertyAgentOutreachStatus,
    ListingAvailabilityStatus,
    AgentResponseIntent,
    AvailabilityVerificationStatus,
    AvailabilityVerificationSource,
)
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.property_availability_verification import (
    ManualVerificationOverrideRequest,
)
from app.services.property_candidate_service import PropertyCandidateService
from app.services.property_matching_config import DEFAULT_MATCHING_CONFIG

logger = logging.getLogger(__name__)


class PropertyAvailabilityVerificationService:
    """
    Module 4 Phase 6: Property Availability Verification Service.
    Responsibilities:
    - Receive validated extraction from PropertyAgentResponseUnderstandingService.
    - Check source message, outreach, listing, and match.
    - Update outreach status to REPLIED (with replied_at timestamp).
    - Create PropertyAvailabilityVerification history record with full provenance.
    - Update PropertyListing facts (asking price, available from, lease, availability).
    - Re-check Phase 3 hard-filter compatibility against tenant requirements if listing facts changed.
    - Mark Phase 4 score STALE if pricing, dates, or lease terms change.
    - Update PropertyMatch verification state (AVAILABLE, UNAVAILABLE, CONDITIONAL, NEEDS_REVIEW).
    - Support authorized operator manual verification overrides.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)
        self.candidate_service = PropertyCandidateService(db)

    def apply_verification_from_extraction(
        self,
        analysis_result: Dict[str, Any],
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Takes the output of PropertyAgentResponseUnderstandingService.analyze_response
        and updates the domain models with full validation, history, and compatibility re-checks.
        """
        correlation = analysis_result.get("correlation", {})
        extraction = analysis_result.get("extraction")
        message_id = uuid.UUID(analysis_result["message_id"])

        # 1. Check if correlation was ambiguous
        if correlation.get("status") == "AMBIGUOUS":
            # Ambiguous reply across multiple active candidate matches
            candidate_ids = correlation.get("candidate_match_ids", [])
            for cid in candidate_ids:
                m = self.db.query(PropertyMatch).filter(PropertyMatch.id == uuid.UUID(cid)).first()
                if m:
                    m.agent_verification_status = "AMBIGUOUS_NEEDS_REVIEW"
                    m.availability_status = "NEEDS_REVIEW"
            self.db.commit()

            self._create_audit_log(
                event_type="AMBIGUOUS_AGENT_REPLY_DETECTED",
                lead_id=None,
                actor_id=actor_id,
                details={
                    "message_id": str(message_id),
                    "candidate_match_ids": candidate_ids,
                    "reason": correlation.get("reason"),
                },
            )

            return {
                "status": "AMBIGUOUS_NEEDS_REVIEW",
                "message_id": str(message_id),
                "candidate_match_ids": candidate_ids,
                "verification": None,
                "score_marked_stale": False,
                "compatibility_rechecked": False,
            }

        if correlation.get("status") != "RESOLVED" or not extraction:
            return {
                "status": "UNRESOLVED",
                "message_id": str(message_id),
                "verification": None,
                "score_marked_stale": False,
                "compatibility_rechecked": False,
            }

        # 2. Load Domain Entities
        match_id = uuid.UUID(correlation["property_match_id"])
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PropertyMatch '{match_id}' not found.",
            )

        listing = match.listing
        lead = match.lead
        outreach_id = uuid.UUID(correlation["outreach_id"]) if correlation.get("outreach_id") else None
        outreach = (
            self.db.query(PropertyAgentOutreach).filter(PropertyAgentOutreach.id == outreach_id).first()
            if outreach_id
            else None
        )
        agent_id = uuid.UUID(correlation["property_agent_id"]) if correlation.get("property_agent_id") else None

        fields = extraction.get("fields", {})
        intent_str = extraction.get("intent", AgentResponseIntent.AVAILABLE.value)
        overall_confidence = extraction.get("overall_confidence", 1.0)
        needs_clarification = extraction.get("needs_clarification", False)

        # 3. Determine Extracted Availability Status
        avail_field = fields.get("availability", {})
        raw_avail = avail_field.get("value")
        if raw_avail:
            availability_status = str(raw_avail).upper()
        elif intent_str == AgentResponseIntent.UNAVAILABLE.value:
            availability_status = "UNAVAILABLE"
        elif intent_str == AgentResponseIntent.CONDITIONAL_AVAILABILITY.value:
            availability_status = "CONDITIONAL"
        elif intent_str == AgentResponseIntent.AVAILABLE.value:
            availability_status = "AVAILABLE"
        else:
            availability_status = "NEEDS_REVIEW"

        # 4. Extract specific terms
        price_field = fields.get("asking_price", {})
        new_price = Decimal(str(price_field["value"])) if "value" in price_field else None
        price_conf = price_field.get("confidence", 1.0)
        currency_field = fields.get("currency", {})
        currency = currency_field.get("value", "SGD")

        date_field = fields.get("available_from", {})
        new_date_str = date_field.get("value")
        new_date = datetime.strptime(new_date_str, "%Y-%m-%d").date() if new_date_str else None

        min_lease_field = fields.get("minimum_lease_months", {})
        new_min_lease = int(min_lease_field["value"]) if "value" in min_lease_field else None

        max_lease_field = fields.get("maximum_lease_months", {})
        new_max_lease = int(max_lease_field["value"]) if "value" in max_lease_field else None

        furnishing_field = fields.get("furnishing", {})
        new_furnishing = furnishing_field.get("value")

        viewing_field = fields.get("viewing_possible", {})
        viewing_possible = viewing_field.get("value") if "value" in viewing_field else None

        viewing_notes_field = fields.get("viewing_notes", {})
        viewing_notes = viewing_notes_field.get("value") if "value" in viewing_notes_field else None

        conditions = fields.get("agent_conditions", {}).get("value")
        restrictions = fields.get("special_restrictions", {}).get("value")

        # 5. Verification Status Determination
        verification_status = AvailabilityVerificationStatus.CONFIRMED.value
        if needs_clarification or price_field.get("needs_confirmation", False):
            verification_status = AvailabilityVerificationStatus.NEEDS_REVIEW.value

        # 6. Create PropertyAvailabilityVerification Record (Preserve Provenance)
        verification = PropertyAvailabilityVerification(
            property_match_id=match.id,
            listing_id=listing.id if listing else None,
            property_agent_id=agent_id,
            outreach_id=outreach.id if outreach else None,
            source_message_id=message_id,
            intent=intent_str,
            availability_status=availability_status,
            asking_price=new_price,
            currency=currency,
            available_from=new_date,
            minimum_lease_months=new_min_lease,
            maximum_lease_months=new_max_lease,
            furnishing=new_furnishing,
            viewing_possible=viewing_possible,
            viewing_notes=viewing_notes,
            conditions={"conditions": conditions} if conditions else None,
            special_restrictions={"restrictions": restrictions} if restrictions else None,
            extracted_fields=fields,
            verification_status=verification_status,
            verification_source=AvailabilityVerificationSource.AGENT_REPLY.value,
            confidence_summary={"overall": overall_confidence, "fields": {k: v.get("confidence") for k, v in fields.items()}},
            overall_confidence=Decimal(str(round(overall_confidence, 3))),
            ai_call_id=uuid.UUID(analysis_result["ai_call_id"]) if analysis_result.get("ai_call_id") else None,
        )
        self.db.add(verification)

        # 7. Update Outreach Record
        was_unresponsive = False
        if outreach:
            if outreach.status == PropertyAgentOutreachStatus.UNRESPONSIVE:
                was_unresponsive = True
            outreach.status = PropertyAgentOutreachStatus.REPLIED
            outreach.replied_at = func_now = datetime.now(timezone.utc)
            if outreach.conversation:
                outreach.conversation.last_message_at = func_now

            # Cancel pending follow-ups for this outreach
            try:
                from app.services.property_agent_followup_service import PropertyAgentFollowUpService
                followup_svc = PropertyAgentFollowUpService(self.db)
                followup_svc.cancel_pending_followups_for_outreach(
                    outreach_id=outreach.id,
                    reason="AGENT_REPLIED",
                    actor_id=actor_id,
                )
                if was_unresponsive:
                    self._create_audit_log(
                        event_type="LATE_AGENT_RESPONSE_PROCESSED",
                        lead_id=match.lead_id,
                        actor_id=actor_id,
                        details={
                            "outreach_id": str(outreach.id),
                            "match_id": str(match.id),
                            "property_agent_id": str(outreach.property_agent_id),
                        },
                    )
            except Exception as e:
                logger.warning(f"Failed to cancel follow-up on reply: {e}")

        # 8. Check for Listing Fact Changes & Update Listing
        facts_changed = False
        old_price = None
        if listing:
            # Price update
            if new_price and price_conf >= 0.70:
                old_price = listing.asking_price
                if old_price != new_price:
                    listing.asking_price = new_price
                    facts_changed = True
                    self._create_audit_log(
                        event_type="LISTING_PRICE_UPDATED_FROM_AGENT",
                        lead_id=match.lead_id,
                        actor_id=actor_id,
                        details={
                            "listing_id": str(listing.id),
                            "old_price": float(old_price) if old_price else None,
                            "new_price": float(new_price),
                            "message_id": str(message_id),
                        },
                    )

            # Available date update
            if new_date:
                if listing.available_from != new_date:
                    listing.available_from = new_date
                    facts_changed = True

            # Lease min update
            if new_min_lease:
                if listing.lease_min_months != new_min_lease:
                    listing.lease_min_months = new_min_lease
                    facts_changed = True

            # Lease max update
            if new_max_lease:
                if listing.lease_max_months != new_max_lease:
                    listing.lease_max_months = new_max_lease
                    facts_changed = True

            # Availability status on listing
            if availability_status == "AVAILABLE":
                listing.availability_status = ListingAvailabilityStatus.AVAILABLE
            elif availability_status == "UNAVAILABLE":
                listing.availability_status = ListingAvailabilityStatus.UNAVAILABLE
            elif availability_status == "CONDITIONAL":
                listing.availability_status = ListingAvailabilityStatus.CONDITIONAL

            listing.source_last_updated_at = datetime.now(timezone.utc)

        # 9. Mark Score Stale if listing facts changed
        score_marked_stale = False
        if facts_changed:
            match.is_stale = True
            match.stale_reason = "Listing terms/pricing updated by agent response."
            score_marked_stale = True

        # 10. Re-check Hard Filters Compatibility against Tenant Requirements
        compatibility_rechecked = False
        compatibility_result = None

        req = (
            self.db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == match.lead_id)
            .first()
        )
        prop = match.property
        source = listing.source if listing else None

        if req and prop and listing and source:
            eval_result = self.candidate_service.evaluate_hard_filters(
                req=req,
                prop=prop,
                listing=listing,
                source=source,
                config=DEFAULT_MATCHING_CONFIG,
            )
            compatibility_rechecked = True
            compatibility_result = eval_result
            match.hard_filter_passed = eval_result["passed"]
            match.hard_filter_result = eval_result

            if availability_status == "UNAVAILABLE":
                match.match_status = PropertyMatchStatus.UNAVAILABLE.value
                match.availability_status = "UNAVAILABLE"
                match.agent_verification_status = "UNAVAILABLE"
                try:
                    from app.services.property_agent_followup_service import PropertyAgentFollowUpService
                    PropertyAgentFollowUpService(self.db).cancel_pending_followups_for_match(
                        match.id,
                        reason="LISTING_UNAVAILABLE",
                        actor_id=actor_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to cancel follow-ups on unavailable: {e}")

                # Module 5 Phase 6: Controlled system cancellation for active viewings
                try:
                    from app.models.viewing import Viewing
                    from app.models.enums import ViewingStatus
                    from app.services.viewing_cancellation_service import ViewingCancellationService
                    active_viewings = (
                        self.db.query(Viewing)
                        .filter(
                            Viewing.property_match_id == match.id,
                            Viewing.status.notin_([
                                ViewingStatus.CANCELLED,
                                ViewingStatus.COMPLETED,
                                ViewingStatus.REJECTED,
                            ]),
                        )
                        .all()
                    )
                    cancel_svc = ViewingCancellationService(self.db)
                    for v in active_viewings:
                        cancel_svc.cancel_viewing(
                            viewing_id=v.id,
                            cancelling_party="SYSTEM",
                            reason_code="PROPERTY_UNAVAILABLE",
                            reason_text="Shortlisted property reported unavailable by agent or listing system",
                            actor_id=actor_id,
                        )
                except Exception as e:
                    logger.warning(f"Failed to cancel viewings on property unavailable: {e}")
            elif not eval_result["passed"]:
                # The agent's updated terms conflict with the tenant requirements!
                # e.g. price increased above tenant budget ceiling or min lease increased
                match.match_status = PropertyMatchStatus.CONDITIONAL.value
                match.availability_status = "CONDITIONAL"
                match.agent_verification_status = "INCOMPATIBLE_WITH_TENANT"
                try:
                    from app.services.property_agent_followup_service import PropertyAgentFollowUpService
                    PropertyAgentFollowUpService(self.db).cancel_pending_followups_for_match(
                        match.id,
                        reason="TERMS_INCOMPATIBLE_WITH_TENANT",
                        actor_id=actor_id,
                    )
                except Exception as e:
                    logger.warning(f"Failed to cancel follow-ups on incompatible: {e}")
                self._create_audit_log(
                    event_type="MATCH_COMPATIBILITY_FAILED_AFTER_AGENT_REPLY",
                    lead_id=match.lead_id,
                    actor_id=actor_id,
                    details={
                        "match_id": str(match.id),
                        "failed_rules": eval_result.get("failed_rules", []),
                        "reason_codes": eval_result.get("reason_codes", []),
                    },
                )
            else:
                # Passed hard filters with new terms!
                if availability_status == "AVAILABLE":
                    match.match_status = PropertyMatchStatus.AVAILABLE.value
                    match.availability_status = "AVAILABLE"
                    match.agent_verification_status = "VERIFIED"
                elif availability_status == "CONDITIONAL":
                    match.match_status = PropertyMatchStatus.CONDITIONAL.value
                    match.availability_status = "CONDITIONAL"
                    match.agent_verification_status = "CONDITIONAL"
                else:
                    match.match_status = PropertyMatchStatus.NEEDS_REVIEW.value
                    match.availability_status = "NEEDS_REVIEW"
                    match.agent_verification_status = "NEEDS_REVIEW"
        else:
            # Fallback status update if requirement/property not joined
            if availability_status == "AVAILABLE":
                match.match_status = PropertyMatchStatus.AVAILABLE.value
                match.availability_status = "AVAILABLE"
                match.agent_verification_status = "VERIFIED"
            elif availability_status == "UNAVAILABLE":
                match.match_status = PropertyMatchStatus.UNAVAILABLE.value
                match.availability_status = "UNAVAILABLE"
                match.agent_verification_status = "UNAVAILABLE"
            else:
                match.match_status = PropertyMatchStatus.NEEDS_REVIEW.value
                match.availability_status = "NEEDS_REVIEW"
                match.agent_verification_status = "NEEDS_REVIEW"

        self.db.commit()
        self.db.refresh(verification)
        self.db.refresh(match)

        self._create_audit_log(
            event_type="PROPERTY_AVAILABILITY_VERIFIED",
            lead_id=match.lead_id,
            actor_id=actor_id,
            details={
                "match_id": str(match.id),
                "verification_id": str(verification.id),
                "availability_status": availability_status,
                "verification_status": verification_status,
                "match_status": match.match_status,
                "score_marked_stale": score_marked_stale,
            },
        )

        return {
            "status": "COMPLETED",
            "message_id": str(message_id),
            "match_id": str(match.id),
            "verification": verification,
            "match_status": match.match_status,
            "availability_status": match.availability_status,
            "score_marked_stale": score_marked_stale,
            "compatibility_rechecked": compatibility_rechecked,
            "compatibility_result": compatibility_result,
        }

    def manual_availability_override(
        self,
        match_id: uuid.UUID,
        request: ManualVerificationOverrideRequest,
        actor_id: str,
    ) -> PropertyAvailabilityVerification:
        """
        Operator manual override of availability verification.
        Requires reason, records provenance source as HUMAN_OPERATOR,
        and never overwrites historical agent records.
        """
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PropertyMatch '{match_id}' not found.",
            )

        listing = match.listing

        # Create verification record
        verification = PropertyAvailabilityVerification(
            property_match_id=match.id,
            listing_id=listing.id if listing else None,
            property_agent_id=listing.agent_id if listing else None,
            availability_status=request.availability_status.upper(),
            asking_price=request.asking_price,
            currency=request.currency or "SGD",
            available_from=request.available_from,
            minimum_lease_months=request.minimum_lease_months,
            maximum_lease_months=request.maximum_lease_months,
            furnishing=request.furnishing,
            viewing_possible=request.viewing_possible,
            viewing_notes=request.viewing_notes,
            conditions=request.conditions,
            special_restrictions=request.special_restrictions,
            verification_status=AvailabilityVerificationStatus.CONFIRMED.value,
            verification_source=AvailabilityVerificationSource.HUMAN_OPERATOR.value,
            overall_confidence=Decimal("1.000"),
            notes=f"Manual operator override by {actor_id}: {request.reason}",
        )
        self.db.add(verification)

        # Update listing if facts provided
        if listing:
            if request.asking_price is not None:
                listing.asking_price = request.asking_price
            if request.available_from is not None:
                listing.available_from = request.available_from
            if request.minimum_lease_months is not None:
                listing.lease_min_months = request.minimum_lease_months
            if request.maximum_lease_months is not None:
                listing.lease_max_months = request.maximum_lease_months
            if request.availability_status.upper() in ["AVAILABLE", "UNAVAILABLE", "CONDITIONAL"]:
                listing.availability_status = ListingAvailabilityStatus(request.availability_status.upper())

        # Update match
        status_clean = request.availability_status.upper()
        if status_clean == "AVAILABLE":
            match.match_status = PropertyMatchStatus.AVAILABLE.value
            match.availability_status = "AVAILABLE"
            match.agent_verification_status = "VERIFIED_MANUAL"
        elif status_clean == "UNAVAILABLE":
            match.match_status = PropertyMatchStatus.UNAVAILABLE.value
            match.availability_status = "UNAVAILABLE"
            match.agent_verification_status = "UNAVAILABLE_MANUAL"
        elif status_clean == "CONDITIONAL":
            match.match_status = PropertyMatchStatus.CONDITIONAL.value
            match.availability_status = "CONDITIONAL"
            match.agent_verification_status = "CONDITIONAL_MANUAL"
        else:
            match.match_status = PropertyMatchStatus.NEEDS_REVIEW.value
            match.availability_status = "NEEDS_REVIEW"
            match.agent_verification_status = "NEEDS_REVIEW"

        match.manual_override = True
        match.manual_override_by = actor_id
        match.manual_override_at = datetime.now(timezone.utc)
        match.manual_override_reason = request.reason

        self.db.commit()
        self.db.refresh(verification)

        self._create_audit_log(
            event_type="MANUAL_AVAILABILITY_OVERRIDE",
            lead_id=match.lead_id,
            actor_id=actor_id,
            details={
                "match_id": str(match.id),
                "verification_id": str(verification.id),
                "new_availability_status": status_clean,
                "reason": request.reason,
            },
        )

        return verification

    def _create_audit_log(
        self,
        event_type: str,
        lead_id: Optional[uuid.UUID],
        actor_id: str,
        details: Dict[str, Any],
    ) -> None:
        try:
            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action=event_type,
                    entity_type="property_match",
                    entity_id=str(details.get("match_id") or lead_id or uuid.uuid4()),
                    new_value=details,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to record audit log for {event_type}: {e}")
