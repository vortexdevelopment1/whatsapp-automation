import logging
import uuid
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.property_match import PropertyMatch
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.enums import (
    PropertyMatchStatus,
    PropertyAgentOutreachStatus,
    PropertyAgentStatus,
    ListingAvailabilityStatus,
)
from app.schemas.audit import AuditLogCreate
from app.repositories.audit_repo import AuditRepository
from app.schemas.property_agent_followup import (
    FallbackPreviewResponse,
    ExecuteFallbackResponse,
)
from app.services.agent_followup_config import (
    AgentFollowUpConfig,
    DEFAULT_AGENT_FOLLOWUP_CONFIG,
)
from app.services.property_candidate_service import PropertyCandidateService
from app.services.property_matching_config import DEFAULT_MATCHING_CONFIG

logger = logging.getLogger(__name__)


class PropertyVerificationFallbackService:
    """
    Coordinates fallback decisions when an outreach agent is unresponsive,
    a listing becomes unavailable, or verification fails:
    1. Check alternate active listings for the same canonical property.
    2. Check next ranked candidate property for the same qualified lead.
    3. Respect total agent contact limits and minimum score thresholds.
    4. Escalate to human operator review if all options are exhausted.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)
        self.candidate_service = PropertyCandidateService(db)

    def preview_fallback(
        self,
        match_id: uuid.UUID,
        config: Optional[AgentFollowUpConfig] = None,
    ) -> FallbackPreviewResponse:
        """
        Determines the recommended fallback action without modifying business state.
        """
        cfg = config or DEFAULT_AGENT_FOLLOWUP_CONFIG
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PropertyMatch '{match_id}' not found.",
            )

        latest_outreach = (
            self.db.query(PropertyAgentOutreach)
            .filter(PropertyAgentOutreach.property_match_id == match_id)
            .order_by(PropertyAgentOutreach.created_at.desc())
            .first()
        )
        current_outreach_status = latest_outreach.status.value if latest_outreach else None

        # Count total agent contacts made for this lead
        total_contacts = (
            self.db.query(PropertyAgentOutreach)
            .filter(PropertyAgentOutreach.lead_id == match.lead_id)
            .count()
        )

        # 1. Global Contact Protection Gate
        if total_contacts >= cfg.max_total_agent_contacts:
            return FallbackPreviewResponse(
                match_id=match.id,
                current_match_status=match.match_status,
                current_outreach_status=current_outreach_status,
                recommended_action="HUMAN_REVIEW",
                reason="MAX_AGENT_CONTACTS_REACHED",
                total_agent_contacts=total_contacts,
                max_total_agent_contacts=cfg.max_total_agent_contacts,
            )

        # 2. Strategy 1: Check Alternate Listing for Same Canonical Property
        if cfg.alternate_listing_enabled and match.property_id:
            prop = match.property or self.db.query(Property).filter(Property.id == match.property_id).first()
            tenant_req = self.db.query(TenantRequirement).filter(TenantRequirement.lead_id == match.lead_id).first()

            alternate_listings = (
                self.db.query(PropertyListing)
                .filter(
                    PropertyListing.property_id == match.property_id,
                    PropertyListing.id != match.listing_id,
                    PropertyListing.listing_status == "ACTIVE",
                    PropertyListing.availability_status != ListingAvailabilityStatus.UNAVAILABLE.value,
                    PropertyListing.agent_id.isnot(None),
                )
                .all()
            )

            for alt_listing in alternate_listings:
                alt_agent = (
                    self.db.query(PropertyAgent)
                    .filter(
                        PropertyAgent.id == alt_listing.agent_id,
                        PropertyAgent.status == PropertyAgentStatus.ACTIVE,
                    )
                    .first()
                )
                if not alt_agent:
                    continue

                # Check if this agent is already unresponsive for this lead
                past_unresponsive = (
                    self.db.query(PropertyAgentOutreach)
                    .filter(
                        PropertyAgentOutreach.lead_id == match.lead_id,
                        PropertyAgentOutreach.property_agent_id == alt_agent.id,
                        PropertyAgentOutreach.status == PropertyAgentOutreachStatus.UNRESPONSIVE,
                    )
                    .first()
                )
                if past_unresponsive:
                    continue

                # Validate hard-filter compatibility
                if prop and tenant_req:
                    source = alt_listing.source or (
                        self.db.query(PropertySource).filter(PropertySource.id == alt_listing.source_id).first()
                        if alt_listing.source_id
                        else None
                    )
                    eval_result = self.candidate_service.evaluate_hard_filters(
                        req=tenant_req,
                        prop=prop,
                        listing=alt_listing,
                        source=source,
                        config=DEFAULT_MATCHING_CONFIG,
                    )
                    if not eval_result["passed"]:
                        continue

                # Eligible alternate listing found!
                return FallbackPreviewResponse(
                    match_id=match.id,
                    current_match_status=match.match_status,
                    current_outreach_status=current_outreach_status,
                    recommended_action="TRY_ALTERNATE_LISTING",
                    reason="Alternate active listing found for same canonical property",
                    alternate_listing={
                        "id": str(alt_listing.id),
                        "property_id": str(alt_listing.property_id),
                        "property_agent_id": str(alt_listing.agent_id),
                        "agent_name": alt_agent.full_name,
                        "agent_phone": alt_agent.phone_normalized,
                        "asking_price": float(alt_listing.asking_price) if alt_listing.asking_price else None,
                        "source_reference": alt_listing.listing_reference or alt_listing.source_listing_id,
                    },
                    total_agent_contacts=total_contacts,
                    max_total_agent_contacts=cfg.max_total_agent_contacts,
                )

        # 3. Strategy 2: Check Next Ranked Candidate Property
        if cfg.alternate_property_enabled:
            candidate_matches = (
                self.db.query(PropertyMatch)
                .filter(
                    PropertyMatch.lead_id == match.lead_id,
                    PropertyMatch.id != match.id,
                    PropertyMatch.hard_filter_passed.is_(True),
                    PropertyMatch.match_status.in_([
                        PropertyMatchStatus.SCORED.value,
                        PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value,
                        PropertyMatchStatus.CANDIDATE.value,
                    ]),
                    PropertyMatch.match_score >= cfg.min_score_for_alternate_property,
                )
                .order_by(
                    PropertyMatch.rank.asc().nullslast(),
                    PropertyMatch.match_score.desc().nullslast(),
                )
                .all()
            )

            for cand in candidate_matches:
                # Ensure no active outreach already exists
                has_active_outreach = (
                    self.db.query(PropertyAgentOutreach)
                    .filter(
                        PropertyAgentOutreach.property_match_id == cand.id,
                        PropertyAgentOutreach.status.in_([
                            PropertyAgentOutreachStatus.SENT,
                            PropertyAgentOutreachStatus.DELIVERED,
                            PropertyAgentOutreachStatus.READ,
                            PropertyAgentOutreachStatus.REPLIED,
                        ]),
                    )
                    .first()
                )
                if has_active_outreach:
                    continue

                # Eligible next property match found!
                return FallbackPreviewResponse(
                    match_id=match.id,
                    current_match_status=match.match_status,
                    current_outreach_status=current_outreach_status,
                    recommended_action="TRY_NEXT_PROPERTY",
                    reason=f"Next ranked candidate property (rank #{cand.rank or '?'}, score {cand.match_score or '?'}) is eligible",
                    next_property_match={
                        "id": str(cand.id),
                        "property_id": str(cand.property_id),
                        "listing_id": str(cand.listing_id) if cand.listing_id else None,
                        "rank": cand.rank,
                        "match_score": float(cand.match_score) if cand.match_score else None,
                    },
                    total_agent_contacts=total_contacts,
                    max_total_agent_contacts=cfg.max_total_agent_contacts,
                )

        # 4. Strategy 3: Human Review Escalation
        return FallbackPreviewResponse(
            match_id=match.id,
            current_match_status=match.match_status,
            current_outreach_status=current_outreach_status,
            recommended_action="HUMAN_REVIEW",
            reason="NO_ELIGIBLE_ALTERNATIVES",
            total_agent_contacts=total_contacts,
            max_total_agent_contacts=cfg.max_total_agent_contacts,
        )

    def execute_fallback(
        self,
        match_id: uuid.UUID,
        config: Optional[AgentFollowUpConfig] = None,
        actor_id: str = "system",
        reason: Optional[str] = None,
    ) -> ExecuteFallbackResponse:
        """
        Executes the recommended fallback action:
        - If TRY_ALTERNATE_LISTING: links match to alternate listing & dispatches initial outreach
        - If TRY_NEXT_PROPERTY: promotes next candidate match & dispatches initial outreach
        - If HUMAN_REVIEW: transitions match to NEEDS_REVIEW with audit log
        """
        cfg = config or DEFAULT_AGENT_FOLLOWUP_CONFIG
        preview = self.preview_fallback(match_id=match_id, config=cfg)
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()

        from app.services.property_agent_outreach_service import PropertyAgentOutreachService
        outreach_svc = PropertyAgentOutreachService(self.db)

        if preview.recommended_action == "TRY_ALTERNATE_LISTING" and preview.alternate_listing:
            alt_listing_id = uuid.UUID(preview.alternate_listing["id"])
            match.listing_id = alt_listing_id
            match.match_status = PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value
            match.agent_verification_status = "READY_FOR_AGENT_VERIFICATION"
            self.db.commit()

            # Dispatch new outreach to alternate agent
            new_outreach = outreach_svc.send_initial_outreach(
                match_id=match.id,
                actor_id=actor_id,
                manual_reason=f"Fallback from unresponsive previous listing. {reason or ''}".strip(),
            )

            self._create_audit_log(
                event_type="ALTERNATE_LISTING_SELECTED",
                lead_id=match.lead_id,
                actor_id=actor_id,
                details={
                    "match_id": str(match.id),
                    "previous_outreach_status": preview.current_outreach_status,
                    "new_listing_id": str(alt_listing_id),
                    "new_outreach_id": str(new_outreach.id),
                    "reason": reason or preview.reason,
                },
            )

            return ExecuteFallbackResponse(
                status="SUCCESS",
                action="TRY_ALTERNATE_LISTING",
                match_id=match.id,
                new_outreach_id=str(new_outreach.id),
                details=preview.alternate_listing,
            )

        elif preview.recommended_action == "TRY_NEXT_PROPERTY" and preview.next_property_match:
            next_match_id = uuid.UUID(preview.next_property_match["id"])
            next_match = self.db.query(PropertyMatch).filter(PropertyMatch.id == next_match_id).first()
            if not next_match:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Next match candidate not found.")

            next_match.match_status = PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value
            next_match.agent_verification_status = "READY_FOR_AGENT_VERIFICATION"
            self.db.commit()

            new_outreach = outreach_svc.send_initial_outreach(
                match_id=next_match.id,
                actor_id=actor_id,
                manual_reason=f"Fallback: next ranked candidate property. {reason or ''}".strip(),
            )

            self._create_audit_log(
                event_type="NEXT_PROPERTY_CANDIDATE_SELECTED",
                lead_id=match.lead_id,
                actor_id=actor_id,
                details={
                    "previous_match_id": str(match.id),
                    "next_match_id": str(next_match.id),
                    "new_outreach_id": str(new_outreach.id),
                    "rank": next_match.rank,
                    "match_score": float(next_match.match_score) if next_match.match_score else None,
                    "reason": reason or preview.reason,
                },
            )

            return ExecuteFallbackResponse(
                status="SUCCESS",
                action="TRY_NEXT_PROPERTY",
                match_id=match.id,
                new_match_id=str(next_match.id),
                new_outreach_id=str(new_outreach.id),
                details=preview.next_property_match,
            )

        else:
            # Human Review Escalation
            match.match_status = PropertyMatchStatus.NEEDS_REVIEW.value
            match.agent_verification_status = "HUMAN_REVIEW"
            self.db.commit()

            self._create_audit_log(
                event_type="HUMAN_REVIEW_REQUESTED",
                lead_id=match.lead_id,
                actor_id=actor_id,
                details={
                    "match_id": str(match.id),
                    "reason": preview.reason,
                    "total_contacts": preview.total_agent_contacts,
                },
            )

            return ExecuteFallbackResponse(
                status="ESCALATED",
                action="HUMAN_REVIEW",
                match_id=match.id,
                details={"reason": preview.reason},
            )

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
                    entity_type="property_verification_fallback",
                    entity_id=str(details.get("match_id") or details.get("new_outreach_id") or lead_id or uuid.uuid4()),
                    new_value=details,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to record audit log for {event_type}: {e}")
