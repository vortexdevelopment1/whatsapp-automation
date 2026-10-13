import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_match import PropertyMatch
from app.models.property_matching_run import PropertyMatchingRun
from app.models.property_availability_verification import PropertyAvailabilityVerification
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_agent_followup import PropertyAgentFollowUp
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
from app.models.enums import (
    QualificationStatus,
    PropertyStatus,
    PropertyListingStatus,
    ListingAvailabilityStatus,
    PropertyMatchStatus,
    ShortlistItemStatus,
    PropertyShortlistStatus,
    ShortlistReasonCode,
    AvailabilityVerificationStatus,
    PropertyAgentOutreachStatus,
)
from app.models.audit_log import AuditLog
from app.services.shortlist_config import ShortlistConfig
from app.schemas.property_shortlist import (
    CandidateReadinessResult,
    PropertyShortlistResponse,
    PropertyShortlistItemResponse,
    PropertyMatchingDashboardResponse,
    DashboardSummaryCards,
    DashboardFunnelStep,
    CandidateComparisonItem,
    CandidateDetailItem,
    Module5HandoffPayload,
    Module5PropertyItem,
)


class PropertyShortlistService:

    @staticmethod
    def evaluate_candidate_readiness(
        match: PropertyMatch,
        requirement: TenantRequirement,
        config: Optional[ShortlistConfig] = None,
    ) -> CandidateReadinessResult:
        """
        Evaluates current candidate readiness considering latest listing status,
        asking price, availability verification, lease compatibility, move-in date,
        and score freshness.
        """
        if config is None:
            config = ShortlistConfig()

        reasons: List[str] = []
        warnings: List[str] = []
        is_eligible = True
        status = ShortlistItemStatus.PENDING_VERIFICATION.value
        requires_refresh = False

        prop: Optional[Property] = match.property
        listing: Optional[PropertyListing] = match.listing

        # 1. Physical Property & Listing Status
        if not prop or prop.status != PropertyStatus.ACTIVE.value:
            reasons.append(ShortlistReasonCode.PROPERTY_INACTIVE.value)
            return CandidateReadinessResult(
                property_match_id=match.id,
                shortlist_status=ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value,
                eligible=False,
                score=match.match_score,
                rank=match.rank,
                reasons=reasons,
                explanation="Physical property is inactive or archived.",
            )

        if not listing or listing.listing_status != PropertyListingStatus.ACTIVE.value:
            reasons.append(ShortlistReasonCode.LISTING_INACTIVE.value)
            return CandidateReadinessResult(
                property_match_id=match.id,
                shortlist_status=ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value,
                eligible=False,
                score=match.match_score,
                rank=match.rank,
                reasons=reasons,
                explanation="Property listing is inactive, stale, or removed.",
            )

        # 2. Hard Filters Baseline
        if match.hard_filter_passed:
            reasons.append(ShortlistReasonCode.HARD_FILTERS_PASS.value)
        else:
            reasons.append(ShortlistReasonCode.PRICE_ABOVE_LIMIT.value)
            is_eligible = False

        # 3. Score Freshness & Minimum Score
        if match.is_stale:
            reasons.append(ShortlistReasonCode.SCORE_STALE.value)
            requires_refresh = True
            if config.require_current_score:
                is_eligible = False

        if match.match_score is not None:
            if match.match_score >= config.minimum_shortlist_score:
                reasons.append(ShortlistReasonCode.STRONG_MATCH_SCORE.value)
            else:
                reasons.append(ShortlistReasonCode.BELOW_MINIMUM_SCORE.value)
                is_eligible = False

        # 4. Latest Price Re-evaluation
        asking_price = listing.asking_price
        budget_max = requirement.budget_max
        if asking_price is not None and budget_max is not None:
            if asking_price <= budget_max:
                reasons.append(ShortlistReasonCode.PRICE_WITHIN_BUDGET.value)
            else:
                diff_pct = ((asking_price - budget_max) / budget_max) * Decimal("100.0")
                if diff_pct <= config.max_budget_tolerance_percentage_conditional and config.allow_conditional_candidates:
                    warnings.append(ShortlistReasonCode.PRICE_NEAR_LIMIT.value)
                else:
                    reasons.append(ShortlistReasonCode.PRICE_ABOVE_LIMIT.value)
                    is_eligible = False

        # 5. Lease Duration Compatibility
        if listing.lease_min_months is not None and requirement.lease_duration_months is not None:
            if listing.lease_min_months <= requirement.lease_duration_months:
                reasons.append(ShortlistReasonCode.LEASE_COMPATIBLE.value)
            else:
                reasons.append(ShortlistReasonCode.LEASE_INCOMPATIBLE.value)
                is_eligible = False

        # 6. Move-in Date Compatibility
        if listing.available_from is not None and requirement.move_in_date is not None:
            if listing.available_from <= requirement.move_in_date:
                reasons.append(ShortlistReasonCode.MOVE_IN_COMPATIBLE.value)
            else:
                delay_days = (listing.available_from - requirement.move_in_date).days
                if delay_days <= config.max_move_in_delay_days_conditional and config.allow_conditional_candidates:
                    warnings.append(ShortlistReasonCode.AVAILABILITY_DATE_SLIGHTLY_LATE.value)
                else:
                    reasons.append(ShortlistReasonCode.MOVE_IN_INCOMPATIBLE.value)
                    is_eligible = False

        # 7. Agent Availability Verification Check
        avail_status = listing.availability_status
        verif_status = match.agent_verification_status

        if avail_status == ListingAvailabilityStatus.UNAVAILABLE.value or match.match_status == PropertyMatchStatus.UNAVAILABLE.value:
            reasons.append(ShortlistReasonCode.LISTING_UNAVAILABLE.value)
            return CandidateReadinessResult(
                property_match_id=match.id,
                shortlist_status=ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value,
                eligible=False,
                score=match.match_score,
                rank=match.rank,
                availability="UNAVAILABLE",
                reasons=reasons,
                warnings=warnings,
                explanation="Property confirmed unavailable by agent or listing record.",
            )

        if not is_eligible:
            return CandidateReadinessResult(
                property_match_id=match.id,
                shortlist_status=ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value,
                eligible=False,
                score=match.match_score,
                rank=match.rank,
                availability=avail_status,
                verification_status=verif_status,
                reasons=reasons,
                warnings=warnings,
                requires_score_refresh=requires_refresh,
                explanation=f"Ineligible for shortlist due to incompatible criteria or stale score: {', '.join(reasons)}",
            )

        # 8. Categorize into VERIFIED, CONDITIONAL, or PENDING
        if verif_status == AvailabilityVerificationStatus.CONFIRMED.value and avail_status == ListingAvailabilityStatus.AVAILABLE.value:
            reasons.append(ShortlistReasonCode.AGENT_CONFIRMED_AVAILABLE.value)
            if warnings and config.allow_conditional_candidates:
                status = ShortlistItemStatus.CONDITIONAL_CANDIDATE.value
                explanation = (
                    f"Conditional candidate: Available from {listing.available_from} "
                    f"at SGD {asking_price:,.0f} with conditions/warnings ({', '.join(warnings)})."
                )
            else:
                status = ShortlistItemStatus.VERIFIED_CANDIDATE.value
                avail_date_str = str(listing.available_from) if listing.available_from else "immediate"
                explanation = (
                    f"Verified strong match. Agent confirmed availability at SGD {asking_price:,.0f} "
                    f"from {avail_date_str}. Within budget, matches {prop.bedrooms}-bedroom {prop.property_type} "
                    f"requirement with compatible {listing.lease_min_months}-month lease."
                )
        elif (
            (avail_status == ListingAvailabilityStatus.CONDITIONAL.value or (warnings and config.allow_conditional_candidates))
            and verif_status in [AvailabilityVerificationStatus.CONFIRMED.value, AvailabilityVerificationStatus.PROPOSED.value]
        ):
            status = ShortlistItemStatus.CONDITIONAL_CANDIDATE.value
            explanation = f"Potential match requiring confirmation: {', '.join(warnings) if warnings else 'conditional availability'}."
        elif match.match_status == PropertyMatchStatus.NEEDS_REVIEW.value:
            status = ShortlistItemStatus.NEEDS_HUMAN_REVIEW.value
            explanation = "Requires operator review before shortlisting."
        elif verif_status in ["UNRESPONSIVE", "AGENT_UNRESPONSIVE"] or match.match_status == PropertyMatchStatus.AGENT_UNRESPONSIVE.value:
            status = ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value
            reasons.append(ShortlistReasonCode.AGENT_NOT_VERIFIED.value)
            explanation = "Agent is unresponsive; candidate ineligible for shortlist."
        else:
            status = ShortlistItemStatus.PENDING_VERIFICATION.value
            reasons.append(ShortlistReasonCode.AGENT_NOT_VERIFIED.value)
            explanation = "Awaiting agent availability confirmation before shortlisting."

        return CandidateReadinessResult(
            property_match_id=match.id,
            shortlist_status=status,
            eligible=True,
            score=match.match_score,
            rank=match.rank,
            availability=avail_status,
            verification_status=verif_status,
            reasons=reasons,
            warnings=warnings,
            explanation=explanation,
            requires_score_refresh=requires_refresh,
        )

    @classmethod
    def build_shortlist(
        cls,
        db: Session,
        lead_id: uuid.UUID,
        config: Optional[ShortlistConfig] = None,
        created_by: Optional[str] = "SYSTEM",
    ) -> PropertyShortlist:
        """
        Builds or refreshes the verified shortlist for a qualified tenant lead.
        """
        if config is None:
            config = ShortlistConfig()

        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        req = (
            db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == lead_id)
            .order_by(desc(TenantRequirement.created_at))
            .first()
        )
        if not req or req.qualification_status != QualificationStatus.QUALIFIED.value:
            raise ValueError(f"Lead {lead_id} is not QUALIFIED for property shortlisting")

        # Archive existing active shortlists
        existing_shortlists = (
            db.query(PropertyShortlist)
            .filter(PropertyShortlist.lead_id == lead_id)
            .all()
        )
        current_version = 1
        for s in existing_shortlists:
            if s.status in [PropertyShortlistStatus.READY.value, PropertyShortlistStatus.DRAFT.value]:
                s.status = PropertyShortlistStatus.ARCHIVED.value
            if s.version >= current_version:
                current_version = s.version + 1

        matches = (
            db.query(PropertyMatch)
            .filter(PropertyMatch.lead_id == lead_id)
            .order_by(PropertyMatch.rank.asc().nullslast(), desc(PropertyMatch.match_score))
            .all()
        )

        evaluated: List[Tuple[PropertyMatch, CandidateReadinessResult]] = []
        for m in matches:
            res = cls.evaluate_candidate_readiness(m, req, config)
            evaluated.append((m, res))

        # Filter candidate pools
        verified_candidates = [
            (m, res) for m, res in evaluated
            if res.shortlist_status == ShortlistItemStatus.VERIFIED_CANDIDATE.value
        ]
        conditional_candidates = [
            (m, res) for m, res in evaluated
            if res.shortlist_status == ShortlistItemStatus.CONDITIONAL_CANDIDATE.value
        ]

        # Sorting
        def sort_key(item: Tuple[PropertyMatch, CandidateReadinessResult]):
            score = item[0].match_score or Decimal("0")
            return score

        verified_candidates.sort(key=sort_key, reverse=True)
        conditional_candidates.sort(key=sort_key, reverse=True)

        selected: List[Tuple[PropertyMatch, CandidateReadinessResult]] = []
        if config.prefer_verified_over_conditional:
            selected.extend(verified_candidates[: config.max_shortlist_size])
            remaining_slots = config.max_shortlist_size - len(selected)
            if remaining_slots > 0 and config.allow_conditional_candidates:
                selected.extend(conditional_candidates[:remaining_slots])
        else:
            combined = verified_candidates + (conditional_candidates if config.allow_conditional_candidates else [])
            combined.sort(key=sort_key, reverse=True)
            selected = combined[: config.max_shortlist_size]

        # Determine overall shortlist status
        has_verified = any(
            res.shortlist_status in [
                ShortlistItemStatus.VERIFIED_CANDIDATE.value,
                ShortlistItemStatus.CONDITIONAL_CANDIDATE.value,
            ]
            for _, res in selected
        )
        shortlist_status = PropertyShortlistStatus.READY.value if has_verified and len(selected) > 0 else PropertyShortlistStatus.DRAFT.value

        matching_run_id = matches[0].matching_run_id if matches else None

        shortlist = PropertyShortlist(
            lead_id=lead_id,
            matching_run_id=matching_run_id,
            version=current_version,
            status=shortlist_status,
            config_version=config.version,
            created_by=created_by,
        )
        db.add(shortlist)
        db.flush()

        for idx, (m, res) in enumerate(selected, start=1):
            # Check for verification ID
            latest_verif = (
                db.query(PropertyAvailabilityVerification)
                .filter(PropertyAvailabilityVerification.property_match_id == m.id)
                .order_by(desc(PropertyAvailabilityVerification.created_at))
                .first()
            )
            item = PropertyShortlistItem(
                shortlist_id=shortlist.id,
                property_match_id=m.id,
                position=idx,
                shortlist_status=res.shortlist_status,
                score_at_selection=m.match_score,
                verification_id=latest_verif.id if latest_verif else None,
                reason_codes=res.reasons,
                warnings=res.warnings,
                explanation=res.explanation,
                manual_override=False,
            )
            db.add(item)

        # Audit log
        audit = AuditLog(
            actor_id=created_by or "SYSTEM",
            action="SHORTLIST_BUILT",
            entity_type="PROPERTY_SHORTLIST",
            entity_id=str(shortlist.id),
            new_value={
                "lead_id": str(lead_id),
                "version": current_version,
                "status": shortlist_status,
                "selected_count": len(selected),
                "verified_count": len(verified_candidates),
                "conditional_count": len(conditional_candidates),
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(shortlist)
        return shortlist

    @classmethod
    def refresh_shortlist(
        cls,
        db: Session,
        lead_id: uuid.UUID,
        config: Optional[ShortlistConfig] = None,
        user_email: Optional[str] = "SYSTEM",
    ) -> PropertyShortlist:
        """
        Re-evaluates latest candidate state and updates or marks shortlist STALE.
        """
        shortlist = (
            db.query(PropertyShortlist)
            .filter(
                PropertyShortlist.lead_id == lead_id,
                PropertyShortlist.status.in_([
                    PropertyShortlistStatus.READY.value,
                    PropertyShortlistStatus.DRAFT.value,
                ]),
            )
            .order_by(desc(PropertyShortlist.version))
            .first()
        )

        req = (
            db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == lead_id)
            .order_by(desc(TenantRequirement.created_at))
            .first()
        )

        if not shortlist:
            return cls.build_shortlist(db, lead_id, config, user_email)

        if not req or req.qualification_status != QualificationStatus.QUALIFIED.value:
            shortlist.status = PropertyShortlistStatus.STALE.value
            db.commit()
            return shortlist

        # Re-evaluate all items
        is_stale = False
        for item in shortlist.items:
            m = item.property_match
            if not m:
                continue
            res = cls.evaluate_candidate_readiness(m, req, config)
            if not res.eligible or res.requires_score_refresh:
                is_stale = True
                item.shortlist_status = ShortlistItemStatus.NOT_SHORTLIST_ELIGIBLE.value
                item.warnings = (item.warnings or []) + ["STATE_STALE_OR_INCOMPATIBLE"]

        if is_stale:
            shortlist.status = PropertyShortlistStatus.STALE.value

        audit = AuditLog(
            actor_id=user_email or "SYSTEM",
            action="SHORTLIST_REFRESHED",
            entity_type="PROPERTY_SHORTLIST",
            entity_id=str(shortlist.id),
            new_value={"status": shortlist.status, "is_stale": is_stale},
        )
        db.add(audit)
        db.commit()
        db.refresh(shortlist)
        return shortlist

    @classmethod
    def add_item_to_shortlist(
        cls,
        db: Session,
        shortlist_id: uuid.UUID,
        property_match_id: uuid.UUID,
        user_email: Optional[str] = "SYSTEM",
        manual_override_reason: Optional[str] = None,
        force_override: bool = False,
    ) -> PropertyShortlistItem:
        """
        Adds a candidate to the active shortlist with strict safety blocks on unavailable candidates.
        """
        shortlist = db.query(PropertyShortlist).filter(PropertyShortlist.id == shortlist_id).first()
        if not shortlist:
            raise ValueError(f"Shortlist {shortlist_id} not found")

        match = db.query(PropertyMatch).filter(PropertyMatch.id == property_match_id).first()
        if not match:
            raise ValueError(f"Property match {property_match_id} not found")

        # Hard safety validation
        if not force_override:
            if match.listing and match.listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE.value:
                raise ValueError("Cannot shortlist an UNAVAILABLE property candidate")
            if match.listing and match.listing.listing_status != PropertyListingStatus.ACTIVE.value:
                raise ValueError("Cannot shortlist an INACTIVE property listing")
            if match.property and match.property.status != PropertyStatus.ACTIVE.value:
                raise ValueError("Cannot shortlist an INACTIVE property")

        # Check if already present
        existing_item = (
            db.query(PropertyShortlistItem)
            .filter(
                PropertyShortlistItem.shortlist_id == shortlist_id,
                PropertyShortlistItem.property_match_id == property_match_id,
            )
            .first()
        )
        if existing_item:
            return existing_item

        next_pos = (
            db.query(PropertyShortlistItem)
            .filter(PropertyShortlistItem.shortlist_id == shortlist_id)
            .count()
        ) + 1

        req = (
            db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == shortlist.lead_id)
            .order_by(desc(TenantRequirement.created_at))
            .first()
        )
        res = cls.evaluate_candidate_readiness(match, req) if req else None

        item = PropertyShortlistItem(
            shortlist_id=shortlist_id,
            property_match_id=property_match_id,
            position=next_pos,
            shortlist_status=res.shortlist_status if res else ShortlistItemStatus.SHORTLISTED.value,
            score_at_selection=match.match_score,
            reason_codes=res.reasons if res else ["MANUAL_ADD"],
            warnings=res.warnings if res else [],
            explanation=res.explanation if res else "Manually added by operator",
            manual_override=True,
            manual_override_reason=manual_override_reason,
        )
        db.add(item)

        audit = AuditLog(
            actor_id=user_email or "SYSTEM",
            action="SHORTLIST_ITEM_ADDED",
            entity_type="PROPERTY_SHORTLIST_ITEM",
            entity_id=str(property_match_id),
            new_value={
                "shortlist_id": str(shortlist_id),
                "position": next_pos,
                "manual_override": True,
                "reason": manual_override_reason,
            },
        )
        db.add(audit)
        db.commit()
        db.refresh(item)
        return item

    @classmethod
    def remove_item_from_shortlist(
        cls,
        db: Session,
        shortlist_id: uuid.UUID,
        property_match_id: uuid.UUID,
        user_email: Optional[str] = "SYSTEM",
        reason: Optional[str] = None,
    ) -> PropertyShortlist:
        """
        Removes an item from the shortlist and re-indexes remaining positions.
        """
        item = (
            db.query(PropertyShortlistItem)
            .filter(
                PropertyShortlistItem.shortlist_id == shortlist_id,
                PropertyShortlistItem.property_match_id == property_match_id,
            )
            .first()
        )
        if not item:
            raise ValueError(f"Item with match {property_match_id} not found in shortlist {shortlist_id}")

        db.delete(item)
        db.flush()

        # Re-index
        remaining = (
            db.query(PropertyShortlistItem)
            .filter(PropertyShortlistItem.shortlist_id == shortlist_id)
            .order_by(PropertyShortlistItem.position.asc())
            .all()
        )
        for idx, it in enumerate(remaining, start=1):
            it.position = idx

        audit = AuditLog(
            actor_id=user_email or "SYSTEM",
            action="SHORTLIST_ITEM_REMOVED",
            entity_type="PROPERTY_SHORTLIST",
            entity_id=str(shortlist_id),
            new_value={"removed_match_id": str(property_match_id), "reason": reason},
        )
        db.add(audit)
        db.commit()

        shortlist = db.query(PropertyShortlist).filter(PropertyShortlist.id == shortlist_id).first()
        return shortlist

    @classmethod
    def reorder_shortlist_items(
        cls,
        db: Session,
        shortlist_id: uuid.UUID,
        ordered_match_ids: List[uuid.UUID],
        user_email: Optional[str] = "SYSTEM",
    ) -> PropertyShortlist:
        """
        Reorders items in a shortlist while preserving original system match ranks.
        """
        items = (
            db.query(PropertyShortlistItem)
            .filter(PropertyShortlistItem.shortlist_id == shortlist_id)
            .all()
        )
        item_map = {item.property_match_id: item for item in items}

        for pos, match_id in enumerate(ordered_match_ids, start=1):
            if match_id in item_map:
                item_map[match_id].position = pos

        audit = AuditLog(
            actor_id=user_email or "SYSTEM",
            action="SHORTLIST_REORDERED",
            entity_type="PROPERTY_SHORTLIST",
            entity_id=str(shortlist_id),
            new_value={"new_order": [str(m) for m in ordered_match_ids]},
        )
        db.add(audit)
        db.commit()

        shortlist = db.query(PropertyShortlist).filter(PropertyShortlist.id == shortlist_id).first()
        return shortlist

    @classmethod
    def get_lead_matching_dashboard(
        cls,
        db: Session,
        lead_id: uuid.UUID,
    ) -> PropertyMatchingDashboardResponse:
        """
        Aggregates lead-level property matching dashboard data with funnel metrics,
        candidate details, requirement comparisons, and Module 5 handoff readiness.
        """
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError(f"Lead {lead_id} not found")

        req = (
            db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == lead_id)
            .order_by(desc(TenantRequirement.created_at))
            .first()
        )

        matches = (
            db.query(PropertyMatch)
            .filter(PropertyMatch.lead_id == lead_id)
            .order_by(PropertyMatch.rank.asc().nullslast(), desc(PropertyMatch.match_score))
            .all()
        )

        shortlist = (
            db.query(PropertyShortlist)
            .filter(
                PropertyShortlist.lead_id == lead_id,
                PropertyShortlist.status.in_([
                    PropertyShortlistStatus.READY.value,
                    PropertyShortlistStatus.DRAFT.value,
                    PropertyShortlistStatus.STALE.value,
                ]),
            )
            .order_by(desc(PropertyShortlist.version))
            .first()
        )

        shortlist_item_map = {}
        if shortlist:
            for it in shortlist.items:
                shortlist_item_map[it.property_match_id] = it

        # Evaluate candidate readiness for all matches
        readiness_map = {}
        for m in matches:
            readiness_map[m.id] = cls.evaluate_candidate_readiness(m, req) if req else None

        # Summary Counts
        total_candidates = len(matches)
        eligible = sum(1 for m in matches if m.hard_filter_passed)
        awaiting = sum(
            1 for m in matches
            if m.match_status == PropertyMatchStatus.AWAITING_AGENT.value
            or (readiness_map[m.id] and readiness_map[m.id].shortlist_status == ShortlistItemStatus.PENDING_VERIFICATION.value)
        )
        verified = sum(
            1 for m in matches
            if readiness_map[m.id] and readiness_map[m.id].shortlist_status == ShortlistItemStatus.VERIFIED_CANDIDATE.value
        )
        conditional = sum(
            1 for m in matches
            if readiness_map[m.id] and readiness_map[m.id].shortlist_status == ShortlistItemStatus.CONDITIONAL_CANDIDATE.value
        )
        unavailable = sum(
            1 for m in matches
            if (m.listing and m.listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE.value)
            or m.match_status == PropertyMatchStatus.UNAVAILABLE.value
            or (readiness_map[m.id] and ShortlistReasonCode.LISTING_UNAVAILABLE.value in readiness_map[m.id].reasons)
        )
        needs_review = sum(
            1 for m in matches
            if m.match_status == PropertyMatchStatus.NEEDS_REVIEW.value
            or m.agent_verification_status == AvailabilityVerificationStatus.NEEDS_REVIEW.value
            or (readiness_map[m.id] and readiness_map[m.id].shortlist_status == ShortlistItemStatus.NEEDS_HUMAN_REVIEW.value)
        )
        shortlisted = len(shortlist.items) if shortlist else 0

        summary = DashboardSummaryCards(
            total_candidates=total_candidates,
            eligible=eligible,
            awaiting_agents=awaiting,
            verified_available=verified,
            conditional=conditional,
            unavailable=unavailable,
            needs_review=needs_review,
            shortlisted=shortlisted,
        )


        # Operational Funnel
        inventory_total = db.query(Property).filter(Property.status == PropertyStatus.ACTIVE.value).count()
        funnel = [
            DashboardFunnelStep(step_name="Inventory Considered", count=inventory_total),
            DashboardFunnelStep(step_name="Hard Filter Eligible", count=eligible),
            DashboardFunnelStep(step_name="Scored", count=sum(1 for m in matches if m.match_score is not None)),
            DashboardFunnelStep(step_name="Agent Contacted", count=sum(1 for m in matches if m.outreach_records)),
            DashboardFunnelStep(step_name="Agent Responded", count=sum(1 for m in matches if m.agent_verification_status in ["CONFIRMED", "REJECTED"])),
            DashboardFunnelStep(step_name="Verified Available", count=verified),
            DashboardFunnelStep(step_name="Shortlisted", count=shortlisted),
        ]

        # Candidates Detail
        candidates_list: List[CandidateDetailItem] = []
        for m in matches:
            prop = m.property
            listing = m.listing
            agent = listing.agent if listing else None
            in_short = m.id in shortlist_item_map
            short_item = shortlist_item_map.get(m.id)

            readiness = cls.evaluate_candidate_readiness(m, req) if req else None

            # Build Comparison
            comp: List[CandidateComparisonItem] = []
            if req and prop and listing:
                # Location
                pref_locs = req.preferred_locations or []
                loc_match = any(loc.lower() in (prop.district or "").lower() or loc.lower() in (prop.address_line_1 or "").lower() or loc.lower() in (prop.address_normalized or "").lower() for loc in pref_locs)
                comp.append(CandidateComparisonItem(
                    field_name="Location",
                    tenant_requirement=", ".join(pref_locs) if pref_locs else "Any",
                    property_value=f"{prop.building_name or prop.address_line_1 or prop.canonical_name} ({prop.district or 'Singapore'})",
                    status="MATCH" if loc_match else "WARNING",
                ))
                # Budget
                b_status = "MATCH"
                if listing.asking_price and req.budget_max:
                    b_status = "MATCH" if listing.asking_price <= req.budget_max else "MISMATCH"
                comp.append(CandidateComparisonItem(
                    field_name="Budget",
                    tenant_requirement=f"<= {req.currency or 'SGD'} {req.budget_max:,.0f}" if req.budget_max else "Any",
                    property_value=f"{listing.currency or 'SGD'} {listing.asking_price:,.0f}" if listing.asking_price else "Unknown",
                    status=b_status,
                ))
                # Bedrooms
                bed_status = "MATCH"
                if listing.property and req.bedrooms:
                    bed_status = "MATCH" if (prop.bedrooms or 0) >= req.bedrooms else "MISMATCH"
                comp.append(CandidateComparisonItem(
                    field_name="Bedrooms",
                    tenant_requirement=str(req.bedrooms) if req.bedrooms else "Any",
                    property_value=str(prop.bedrooms) if prop.bedrooms is not None else "Unknown",
                    status=bed_status,
                ))
                # Move-in
                mi_status = "MATCH"
                if listing.available_from and req.move_in_date:
                    if listing.available_from <= req.move_in_date:
                        mi_status = "MATCH"
                    elif (listing.available_from - req.move_in_date).days <= 14:
                        mi_status = "WARNING"
                    else:
                        mi_status = "MISMATCH"
                comp.append(CandidateComparisonItem(
                    field_name="Move-in",
                    tenant_requirement=str(req.move_in_date) if req.move_in_date else "Flexible",
                    property_value=str(listing.available_from) if listing.available_from else "Unknown",
                    status=mi_status,
                ))
                # Lease
                l_status = "MATCH"
                if listing.lease_min_months and req.lease_duration_months:
                    l_status = "MATCH" if listing.lease_min_months <= req.lease_duration_months else "MISMATCH"
                comp.append(CandidateComparisonItem(
                    field_name="Lease",
                    tenant_requirement=f"{req.lease_duration_months} months" if req.lease_duration_months else "Any",
                    property_value=f"{listing.lease_min_months} months" if listing.lease_min_months else "Unknown",
                    status=l_status,
                ))

            # Latest follow-up status
            latest_fu = m.followup_records[0] if m.followup_records else None
            latest_verif = m.verification_records[0] if m.verification_records else None

            candidate_item = CandidateDetailItem(
                property_match_id=m.id,
                property_id=prop.id if prop else uuid.uuid4(),
                listing_id=listing.id if listing else None,
                property_agent_id=agent.id if agent else None,
                system_rank=m.rank,
                match_score=m.match_score,
                is_stale=m.is_stale,
                stale_reason=m.stale_reason,
                property_name=prop.canonical_name if prop else "Unknown",
                building_name=prop.building_name if prop else None,
                address=prop.address_normalized or prop.address_line_1 or prop.canonical_name or "Unknown",
                district=prop.district if prop else None,
                property_type=prop.property_type if prop else "CONDO",
                bedrooms=prop.bedrooms if prop else None,
                bathrooms=prop.bathrooms if prop else None,
                size_sqft=prop.size_sqft if prop else None,
                furnishing=prop.furnishing if prop else None,
                asking_price=listing.asking_price if listing else None,
                currency=listing.currency if listing else "SGD",
                available_from=listing.available_from if listing else None,
                lease_min_months=listing.lease_min_months if listing else None,
                availability_status=listing.availability_status if listing else None,
                agent_verification_status=m.agent_verification_status,
                agent_name=agent.full_name if agent else None,
                agent_agency=agent.agency_name if agent else None,
                followup_status=latest_fu.status if latest_fu else None,
                shortlist_status=short_item.shortlist_status if short_item else (readiness.shortlist_status if readiness else "NOT_EVALUATED"),
                in_shortlist=in_short,
                shortlist_position=short_item.position if short_item else None,
                explanation=readiness.explanation if readiness else m.scoring_explanation,
                reasons=readiness.reasons if readiness else [],
                warnings=readiness.warnings if readiness else [],
                comparison=comp,
                verified_at=latest_verif.created_at if latest_verif else None,
            )
            candidates_list.append(candidate_item)

        # Enriched Shortlist Response
        shortlist_resp = None
        if shortlist:
            items_enriched: List[PropertyShortlistItemResponse] = []
            for it in shortlist.items:
                m = it.property_match
                p = m.property if m else None
                l = m.listing if m else None
                a = l.agent if l else None
                v = it.verification
                items_enriched.append(PropertyShortlistItemResponse(
                    id=it.id,
                    shortlist_id=it.shortlist_id,
                    property_match_id=it.property_match_id,
                    position=it.position,
                    shortlist_status=it.shortlist_status,
                    score_at_selection=it.score_at_selection,
                    verification_id=it.verification_id,
                    reason_codes=it.reason_codes,
                    warnings=it.warnings,
                    explanation=it.explanation,
                    manual_override=it.manual_override,
                    manual_override_reason=it.manual_override_reason,
                    created_at=it.created_at,
                    updated_at=it.updated_at,
                    property_id=p.id if p else None,
                    listing_id=l.id if l else None,
                    property_agent_id=a.id if a else None,
                    property_name=p.canonical_name if p else None,
                    property_address=p.address_normalized or p.address_line_1 or p.canonical_name if p else None,
                    building_name=p.building_name if p else None,
                    district=p.district if p else None,
                    property_type=p.property_type if p else None,
                    bedrooms=p.bedrooms if p else None,
                    bathrooms=p.bathrooms if p else None,
                    size_sqft=p.size_sqft if p else None,
                    furnishing=p.furnishing if p else None,
                    asking_price=l.asking_price if l else None,
                    currency=l.currency if l else "SGD",
                    available_from=l.available_from if l else None,
                    lease_min_months=l.lease_min_months if l else None,
                    availability_status=l.availability_status if l else None,
                    agent_name=a.full_name if a else None,
                    agent_agency=a.agency_name if a else None,
                    verified_at=v.created_at if v else None,
                ))

            shortlist_resp = PropertyShortlistResponse(
                id=shortlist.id,
                lead_id=shortlist.lead_id,
                matching_run_id=shortlist.matching_run_id,
                version=shortlist.version,
                status=shortlist.status,
                config_version=shortlist.config_version,
                created_by=shortlist.created_by,
                created_at=shortlist.created_at,
                updated_at=shortlist.updated_at,
                items=items_enriched,
            )

        module5_ready = (
            shortlist is not None
            and shortlist.status == PropertyShortlistStatus.READY.value
            and len(shortlist.items) > 0
            and req is not None
            and req.qualification_status == QualificationStatus.QUALIFIED.value
        )

        matching_run = matches[0].matching_run if matches else None

        return PropertyMatchingDashboardResponse(
            lead_id=lead_id,
            tenant_name=lead.phone,
            qualification_status=req.qualification_status if req else "UNKNOWN",
            matching_status="MATCHED" if matches else "NO_MATCHES",
            last_matching_run_at=matching_run.created_at if matching_run else None,
            current_shortlist_status=shortlist.status if shortlist else None,
            current_shortlist_version=shortlist.version if shortlist else None,
            current_shortlist_id=shortlist.id if shortlist else None,
            module5_ready=module5_ready,
            summary=summary,
            funnel=funnel,
            shortlist=shortlist_resp,
            candidates=candidates_list,
        )

    @classmethod
    def generate_module5_handoff(
        cls,
        db: Session,
        lead_id: uuid.UUID,
    ) -> Module5HandoffPayload:
        """
        Generates the authoritative handoff payload for Module 5 viewing coordination.
        """
        shortlist = (
            db.query(PropertyShortlist)
            .filter(
                PropertyShortlist.lead_id == lead_id,
                PropertyShortlist.status == PropertyShortlistStatus.READY.value,
            )
            .order_by(desc(PropertyShortlist.version))
            .first()
        )
        if not shortlist:
            raise ValueError(f"No READY shortlist found for lead {lead_id}")

        req = (
            db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == lead_id)
            .order_by(desc(TenantRequirement.created_at))
            .first()
        )
        if not req or req.qualification_status != QualificationStatus.QUALIFIED.value:
            raise ValueError(f"Tenant requirement for lead {lead_id} is not QUALIFIED")

        prop_items: List[Module5PropertyItem] = []
        for it in shortlist.items:
            m = it.property_match
            if not m or not m.listing or not m.property:
                continue

            # Invariant check: only shortlist eligible items
            if it.shortlist_status not in [
                ShortlistItemStatus.VERIFIED_CANDIDATE.value,
                ShortlistItemStatus.CONDITIONAL_CANDIDATE.value,
                ShortlistItemStatus.SHORTLISTED.value,
            ]:
                continue

            prop_items.append(Module5PropertyItem(
                property_match_id=m.id,
                property_id=m.property_id,
                listing_id=m.listing_id,
                property_agent_id=m.listing.agent_id,
                shortlist_position=it.position,
                match_score=it.score_at_selection or m.match_score,
                availability=m.listing.availability_status.value if hasattr(m.listing.availability_status, 'value') else str(m.listing.availability_status or "AVAILABLE"),
                asking_price=m.listing.asking_price,
                currency=m.listing.currency or "SGD",
                available_from=m.listing.available_from,
                minimum_lease_months=m.listing.lease_min_months or 12,
                verification_id=it.verification_id,
                verified_at=it.verification.created_at if it.verification else None,
            ))

        tenant_req_dict = {

            "preferred_locations": req.preferred_locations or [],
            "budget_max": float(req.budget_max) if req.budget_max else None,
            "currency": req.currency or "SGD",
            "property_type": req.property_type or "CONDO",
            "bedrooms": req.bedrooms,
            "move_in_date": str(req.move_in_date) if req.move_in_date else None,
            "lease_duration_months": req.lease_duration_months or 12,
            "occupants": req.occupants or 1,
            "furnishing": req.furnishing or "FURNISHED",
        }

        return Module5HandoffPayload(
            lead_id=lead_id,
            shortlist_id=shortlist.id,
            shortlist_version=shortlist.version,
            qualification_status=req.qualification_status,
            shortlist_status=shortlist.status,
            handoff_status="READY_FOR_VIEWING_COORDINATION",
            generated_at=datetime.now(timezone.utc),
            tenant_requirements=tenant_req_dict,
            properties=prop_items,
        )
