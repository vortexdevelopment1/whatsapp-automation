import uuid
from datetime import datetime, timezone, date
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_match import PropertyMatch
from app.models.property_matching_run import PropertyMatchingRun
from app.models.enums import (
    QualificationStatus,
    PropertyMatchStatus,
    ScoringReasonCode,
    MissingDataScoringPolicy,
    ListingAvailabilityStatus,
)
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.services.property_scoring_config import PropertyScoringConfig, DEFAULT_SCORING_CONFIG


class PropertyMatchingService:
    """
    Module 4 Phase 4: Property Scoring, Ranking, and Match Explainability.
    Scores ONLY the candidate properties that passed Phase 3 hard filters.
    """

    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    def score_and_rank_lead_candidates(
        self,
        lead_id: uuid.UUID,
        config: Optional[PropertyScoringConfig] = None,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Calculates multidimensional scores and assigns ranks to Phase 3 eligible candidates.
        """
        scoring_config = config or DEFAULT_SCORING_CONFIG

        # 1. Verification: Lead must exist and be QUALIFIED
        lead = (
            self.db.query(Lead)
            .options(joinedload(Lead.tenant_requirement))
            .filter(Lead.id == lead_id)
            .first()
        )
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead '{lead_id}' not found.",
            )

        req: Optional[TenantRequirement] = lead.tenant_requirement
        if not req or req.qualification_status != QualificationStatus.QUALIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lead '{lead_id}' is not QUALIFIED. Only verified qualified tenant leads can be scored.",
            )

        # 2. Query candidates: MUST have passed Phase 3 hard filters
        # A failed hard filter candidate must NEVER be scored.
        candidate_matches = (
            self.db.query(PropertyMatch)
            .options(
                joinedload(PropertyMatch.property),
                joinedload(PropertyMatch.listing),
            )
            .filter(
                PropertyMatch.lead_id == lead_id,
                PropertyMatch.hard_filter_passed.is_(True),
                PropertyMatch.match_status != PropertyMatchStatus.FILTERED_OUT.value,
            )
            .all()
        )

        if not candidate_matches:
            return {
                "lead_id": str(lead_id),
                "scored": 0,
                "ready_for_agent_verification": 0,
                "below_threshold": 0,
                "top_score": None,
                "scoring_config_version": scoring_config.scoring_config_version,
            }

        # 3. Log Scoring Started
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_SCORING_RUN_STARTED",
                entity_type="lead",
                entity_id=str(lead_id),
                new_value={
                    "candidate_count": len(candidate_matches),
                    "config_version": scoring_config.scoring_config_version,
                },
            )
        )

        # 4. Score Each Candidate
        scored_items: List[Tuple[PropertyMatch, float, Dict[str, Any]]] = []

        for match in candidate_matches:
            prop = match.property
            listing = match.listing

            if not prop or not listing:
                continue

            score_res = self.calculate_candidate_score(req, prop, listing, scoring_config)
            scored_items.append((match, score_res["final_score"], score_res))

        # 5. Deterministic Tie-Breaking & Ranking
        # Tie breakers:
        # 1. final_score DESC
        # 2. confirmed AVAILABLE first
        # 3. closer budget fit (|asking_price - budget_max|) ASC
        # 4. data completeness DESC
        # 5. stable UUID string
        target_budget = float(req.budget_max) if req.budget_max else 0.0

        def sort_key(item: Tuple[PropertyMatch, float, Dict[str, Any]]) -> Tuple:
            m, final_score, _ = item
            l = m.listing
            is_avail = 1 if (l and l.availability_status == ListingAvailabilityStatus.AVAILABLE) else 0
            price_diff = abs(float(l.asking_price or 0.0) - target_budget) if l else 999999.0
            completeness = 0
            if m.property:
                completeness += sum(1 for v in [m.property.building_name, m.property.bathrooms, m.property.size_sqft] if v is not None)
            if l:
                completeness += sum(1 for v in [l.available_from, l.lease_min_months, l.lease_max_months] if v is not None)

            return (
                -final_score,
                -is_avail,
                price_diff,
                -completeness,
                str(m.property_id),
                str(m.listing_id or uuid.uuid4()),
            )

        scored_items.sort(key=sort_key)

        ready_count = 0
        below_count = 0

        # 6. Apply Ranks, Thresholds, and Status Updates
        for idx, (match, final_score, breakdown) in enumerate(scored_items, start=1):
            match.rank = idx
            match.match_score = Decimal(str(final_score))
            match.score_breakdown = breakdown
            match.scoring_explanation = breakdown.get("explanation")
            match.scoring_config_version = scoring_config.scoring_config_version
            match.is_stale = False
            match.stale_reason = None

            # Threshold status classification
            if final_score >= scoring_config.minimum_score_for_outreach:
                if idx <= scoring_config.maximum_candidates_for_agent_verification:
                    match.match_status = PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value
                    ready_count += 1
                else:
                    match.match_status = PropertyMatchStatus.SCORED.value
            else:
                match.match_status = PropertyMatchStatus.BELOW_OUTREACH_THRESHOLD.value
                below_count += 1

        top_score = scored_items[0][1] if scored_items else None

        # 7. Update Matching Run record if associated
        latest_run_id = candidate_matches[0].matching_run_id if candidate_matches else None
        if latest_run_id:
            m_run = self.db.query(PropertyMatchingRun).filter(PropertyMatchingRun.id == latest_run_id).first()
            if m_run:
                m_run.scored_candidates = len(scored_items)
                m_run.ready_for_verification_candidates = ready_count
                m_run.below_threshold_candidates = below_count
                m_run.scoring_config_version = scoring_config.scoring_config_version
                if top_score is not None:
                    m_run.top_score = Decimal(str(top_score))

        self.db.commit()

        # 8. Audit Completed
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_SCORING_RUN_COMPLETED",
                entity_type="lead",
                entity_id=str(lead_id),
                new_value={
                    "scored": len(scored_items),
                    "ready_for_verification": ready_count,
                    "below_threshold": below_count,
                    "top_score": top_score,
                    "config_version": scoring_config.scoring_config_version,
                },
            )
        )

        return {
            "lead_id": str(lead_id),
            "scored": len(scored_items),
            "ready_for_agent_verification": ready_count,
            "below_threshold": below_count,
            "top_score": top_score,
            "scoring_config_version": scoring_config.scoring_config_version,
        }

    def calculate_candidate_score(
        self,
        req: TenantRequirement,
        prop: Property,
        listing: PropertyListing,
        config: PropertyScoringConfig,
    ) -> Dict[str, Any]:
        """
        Calculates dimension scores and generates transparent explanations and risk flags.
        """
        dimensions: Dict[str, Any] = {}
        reason_codes: List[str] = []
        positive_factors: List[str] = []
        risks: List[str] = []

        # -------------------------------------------------------------
        # 1. Location Fit (Weight: config.location_weight)
        # -------------------------------------------------------------
        loc_score, loc_reason, loc_code = self._score_location(req, prop, config)
        dimensions["location"] = {
            "raw_score": round(loc_score, 2),
            "weight": config.location_weight,
            "weighted_score": round(loc_score * config.location_weight, 2),
            "reason": loc_reason,
        }
        if loc_code:
            reason_codes.append(loc_code)
            if "EXACT" in loc_code or "PREFERRED" in loc_code:
                positive_factors.append(f"Located in preferred area ({loc_reason})")

        # -------------------------------------------------------------
        # 2. Budget Fit (Weight: config.budget_weight)
        # -------------------------------------------------------------
        budget_score, budget_reason, budget_code = self._score_budget(req, listing, config)
        dimensions["budget"] = {
            "raw_score": round(budget_score, 2),
            "weight": config.budget_weight,
            "weighted_score": round(budget_score * config.budget_weight, 2),
            "reason": budget_reason,
        }
        if budget_code:
            reason_codes.append(budget_code)
            if budget_code == ScoringReasonCode.STRONG_BUDGET_FIT.value:
                positive_factors.append(f"Rental price ({listing.asking_price} {listing.currency}) offers strong budget value")
            elif budget_code == ScoringReasonCode.BUDGET_EXACT_FIT.value:
                positive_factors.append("Rental price matches tenant target budget")
            elif budget_code == ScoringReasonCode.NEAR_BUDGET_LIMIT.value:
                risks.append(f"Asking rent ({listing.asking_price} {listing.currency}) is near upper budget tolerance")

        # -------------------------------------------------------------
        # 3. Property Type Fit (Weight: config.property_type_weight)
        # -------------------------------------------------------------
        pt_score, pt_reason, pt_code = self._score_property_type(req, prop, config)
        dimensions["property_type"] = {
            "raw_score": round(pt_score, 2),
            "weight": config.property_type_weight,
            "weighted_score": round(pt_score * config.property_type_weight, 2),
            "reason": pt_reason,
        }
        if pt_code:
            reason_codes.append(pt_code)
            if pt_code == ScoringReasonCode.EXACT_PROPERTY_TYPE.value:
                positive_factors.append(f"Exact property type match ({prop.property_type.value if hasattr(prop.property_type, 'value') else prop.property_type})")

        # -------------------------------------------------------------
        # 4. Bedrooms Fit (Weight: config.bedrooms_weight)
        # -------------------------------------------------------------
        bed_score, bed_reason, bed_code = self._score_bedrooms(req, prop, config)
        dimensions["bedrooms"] = {
            "raw_score": round(bed_score, 2),
            "weight": config.bedrooms_weight,
            "weighted_score": round(bed_score * config.bedrooms_weight, 2),
            "reason": bed_reason,
        }
        if bed_code:
            reason_codes.append(bed_code)
            if bed_code == ScoringReasonCode.EXACT_BEDROOM_MATCH.value:
                positive_factors.append(f"Exact bedroom requirement met ({prop.bedrooms} BR)")
            elif bed_code == ScoringReasonCode.EXTRA_BEDROOM.value:
                positive_factors.append(f"Offers extra space ({prop.bedrooms} BR vs {req.bedrooms} BR requested)")

        # -------------------------------------------------------------
        # 5. Move-in Date Fit (Weight: config.move_in_weight)
        # -------------------------------------------------------------
        move_score, move_reason, move_code = self._score_move_in(req, listing, config)
        dimensions["move_in"] = {
            "raw_score": round(move_score, 2),
            "weight": config.move_in_weight,
            "weighted_score": round(move_score * config.move_in_weight, 2),
            "reason": move_reason,
        }
        if move_code:
            reason_codes.append(move_code)
            if move_code == ScoringReasonCode.AVAILABLE_BY_MOVE_IN.value:
                positive_factors.append("Available before or on preferred move-in date")
            elif move_code == ScoringReasonCode.AVAILABLE_AFTER_PREFERRED_DATE.value:
                risks.append(f"Available date ({listing.available_from}) is slightly after tenant target ({req.move_in_date})")

        # -------------------------------------------------------------
        # 6. Lease Duration Fit (Weight: config.lease_weight)
        # -------------------------------------------------------------
        lease_score, lease_reason, lease_code = self._score_lease(req, listing, config)
        dimensions["lease"] = {
            "raw_score": round(lease_score, 2),
            "weight": config.lease_weight,
            "weighted_score": round(lease_score * config.lease_weight, 2),
            "reason": lease_reason,
        }
        if lease_code:
            reason_codes.append(lease_code)
            if lease_code == ScoringReasonCode.LEASE_FULLY_COMPATIBLE.value:
                positive_factors.append(f"Lease terms fully support {req.lease_duration_months} months")
            elif lease_code == ScoringReasonCode.OPTIONAL_DATA_MISSING.value:
                risks.append("Listing lease term minimum not specified on record")

        # -------------------------------------------------------------
        # 7. Furnishing Fit (Weight: config.furnishing_weight)
        # -------------------------------------------------------------
        furn_score, furn_reason, furn_code = self._score_furnishing(req, prop, config)
        dimensions["furnishing"] = {
            "raw_score": round(furn_score, 2),
            "weight": config.furnishing_weight,
            "weighted_score": round(furn_score * config.furnishing_weight, 2),
            "reason": furn_reason,
        }
        if furn_code:
            reason_codes.append(furn_code)
            if furn_code == ScoringReasonCode.FURNISHING_MATCH.value:
                positive_factors.append("Furnishing status matches preference")

        # -------------------------------------------------------------
        # 8. Availability Status Fit (Weight: config.availability_weight)
        # -------------------------------------------------------------
        avail_score, avail_reason, avail_code = self._score_availability(listing, config)
        dimensions["availability"] = {
            "raw_score": round(avail_score, 2),
            "weight": config.availability_weight,
            "weighted_score": round(avail_score * config.availability_weight, 2),
            "reason": avail_reason,
        }
        if avail_code:
            reason_codes.append(avail_code)
            if avail_code == ScoringReasonCode.CONFIRMED_AVAILABLE.value:
                positive_factors.append("Availability is confirmed active")
            elif avail_code == ScoringReasonCode.AVAILABILITY_UNVERIFIED.value:
                risks.append("Listing availability not yet verified with agent (Phase 5 outreach required)")

        # Calculate Final Weighted Score (0 to 100)
        final_score = sum(d["weighted_score"] for d in dimensions.values())
        final_score = round(max(0.0, min(100.0, final_score)), 1)

        # Human-readable Explanation synthesis
        pos_str = ", ".join(positive_factors) if positive_factors else "Matches basic eligible criteria"
        explanation = f"Suitable match: {pos_str}."
        if risks:
            explanation += f" Warning: {'; '.join(risks)}."

        return {
            "final_score": final_score,
            "dimensions": dimensions,
            "reason_codes": reason_codes,
            "positive_factors": positive_factors,
            "risks": risks,
            "explanation": explanation,
        }

    # -----------------------------------------------------------------
    # Dimension Scoring Helpers
    # -----------------------------------------------------------------

    def _score_location(
        self, req: TenantRequirement, prop: Property, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        if not req.preferred_locations or len(req.preferred_locations) == 0:
            return 1.0, "no_specific_preferred_location", ScoringReasonCode.EXACT_LOCATION_MATCH.value

        prop_text = " ".join([
            prop.canonical_name or "",
            prop.building_name or "",
            prop.address_line_1 or "",
            prop.address_line_2 or "",
            prop.city or "",
            prop.district or "",
        ]).upper()

        # Check primary preferred location (first in list)
        primary = req.preferred_locations[0].strip().upper()
        if primary and primary in prop_text:
            return 1.0, f"exact_primary_preferred_area_{primary}", ScoringReasonCode.EXACT_LOCATION_MATCH.value

        # Check secondary preferred locations
        for sec in req.preferred_locations[1:]:
            s_clean = sec.strip().upper()
            if s_clean and s_clean in prop_text:
                return 0.9, f"secondary_preferred_area_{s_clean}", ScoringReasonCode.PREFERRED_LOCATION_MATCH.value

        # Postal zone or adjacent district matching
        if prop.postal_code:
            return 0.75, "nearby_postal_area_match", ScoringReasonCode.NEARBY_LOCATION_MATCH.value

        # Optional data missing / fallback
        if config.missing_data_policy == MissingDataScoringPolicy.REDUCED:
            return 0.3, "unmatched_location_reduced", ScoringReasonCode.OPTIONAL_DATA_MISSING.value
        return 0.5, "unmatched_location_neutral", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

    def _score_budget(
        self, req: TenantRequirement, listing: PropertyListing, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        if not listing.asking_price or not req.budget_max:
            return 0.5, "price_or_budget_missing", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

        price = float(listing.asking_price)
        b_max = float(req.budget_max)
        b_min = float(req.budget_min) if req.budget_min else (b_max * 0.7)

        if price <= b_min:
            return 1.0, f"price_{price}_below_or_at_target_range", ScoringReasonCode.STRONG_BUDGET_FIT.value

        if price <= b_max:
            # Linear scale from 1.0 at b_min down to 0.9 at b_max
            ratio = (price - b_min) / max(1.0, (b_max - b_min))
            raw = 1.0 - (0.1 * ratio)
            return raw, f"price_{price}_within_budget_max_{b_max}", ScoringReasonCode.STRONG_BUDGET_FIT.value

        # price > b_max: Allowed only if Phase 3 hard-filter tolerance allowed it
        # Drop score steeply from 0.85 to 0.5
        overshoot = price - b_max
        max_allowed_excess = b_max * 0.10  # assume up to 10% tolerance boundary
        ratio = min(1.0, overshoot / max(1.0, max_allowed_excess))
        raw = 0.85 - (0.35 * ratio)
        return max(0.4, raw), f"price_{price}_above_budget_max_{b_max}_in_tolerance", ScoringReasonCode.NEAR_BUDGET_LIMIT.value

    def _score_property_type(
        self, req: TenantRequirement, prop: Property, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        if not req.property_type or not prop.property_type:
            return 0.7, "property_type_unspecified", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

        req_pt = req.property_type.value if hasattr(req.property_type, "value") else str(req.property_type)
        prop_pt = prop.property_type.value if hasattr(prop.property_type, "value") else str(prop.property_type)

        if req_pt.upper() == prop_pt.upper():
            return 1.0, f"exact_match_{prop_pt}", ScoringReasonCode.EXACT_PROPERTY_TYPE.value

        return 0.8, f"compatible_type_{prop_pt}_for_{req_pt}", ScoringReasonCode.COMPATIBLE_PROPERTY_TYPE.value

    def _score_bedrooms(
        self, req: TenantRequirement, prop: Property, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        if req.bedrooms is None or prop.bedrooms is None:
            return 0.7, "bedrooms_unspecified", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

        if prop.bedrooms == req.bedrooms:
            return 1.0, f"exact_bedroom_match_{prop.bedrooms}", ScoringReasonCode.EXACT_BEDROOM_MATCH.value

        if prop.bedrooms > req.bedrooms:
            score = 1.0 if config.extra_bedroom_policy == "EQUAL" else 0.95
            return score, f"extra_bedrooms_{prop.bedrooms}_gt_{req.bedrooms}", ScoringReasonCode.EXTRA_BEDROOM.value

        # Below requested (should have been filtered, but keep safe fallback)
        return 0.3, f"fewer_bedrooms_{prop.bedrooms}_lt_{req.bedrooms}", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

    def _score_move_in(
        self, req: TenantRequirement, listing: PropertyListing, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        if not req.move_in_date:
            return 1.0, "no_move_in_date_constraint", ScoringReasonCode.AVAILABLE_BY_MOVE_IN.value

        if not listing.available_from:
            if config.missing_data_policy == MissingDataScoringPolicy.REDUCED:
                return 0.4, "available_from_unknown_reduced", ScoringReasonCode.OPTIONAL_DATA_MISSING.value
            return 0.6, "available_from_unknown_neutral", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

        if listing.available_from <= req.move_in_date:
            return 1.0, f"available_{listing.available_from}_before_or_on_{req.move_in_date}", ScoringReasonCode.AVAILABLE_BY_MOVE_IN.value

        # Later than desired move-in date
        days_late = (listing.available_from - req.move_in_date).days
        # Scale down between 0.85 and 0.5
        ratio = min(1.0, days_late / 30.0)
        raw = 0.85 - (0.35 * ratio)
        return max(0.4, raw), f"available_{days_late}_days_after_move_in", ScoringReasonCode.AVAILABLE_AFTER_PREFERRED_DATE.value

    def _score_lease(
        self, req: TenantRequirement, listing: PropertyListing, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        if not req.lease_duration_months:
            return 1.0, "no_lease_duration_constraint", ScoringReasonCode.LEASE_FULLY_COMPATIBLE.value

        if listing.lease_min_months is None:
            if config.missing_data_policy == MissingDataScoringPolicy.REDUCED:
                return 0.4, "lease_terms_unknown_reduced", ScoringReasonCode.OPTIONAL_DATA_MISSING.value
            return 0.6, "lease_terms_unknown_neutral", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

        if listing.lease_min_months <= req.lease_duration_months:
            max_m = listing.lease_max_months or 999
            if req.lease_duration_months <= max_m:
                return 1.0, f"lease_{req.lease_duration_months}m_fully_supported", ScoringReasonCode.LEASE_FULLY_COMPATIBLE.value

        return 0.5, "lease_terms_partial_fit", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

    def _score_furnishing(
        self, req: TenantRequirement, prop: Property, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        req_f = (req.furnishing.value if hasattr(req.furnishing, "value") else str(req.furnishing or "")).upper()
        prop_f = (prop.furnishing.value if hasattr(prop.furnishing, "value") else str(prop.furnishing or "")).upper()

        if not req_f or req_f == "FLEXIBLE":
            return 1.0, "tenant_flexible_on_furnishing", ScoringReasonCode.FURNISHING_MATCH.value

        if not prop_f or prop_f == "UNKNOWN":
            return 0.5, "property_furnishing_unknown", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

        if req_f == prop_f:
            return 1.0, f"exact_furnishing_match_{prop_f}", ScoringReasonCode.FURNISHING_MATCH.value

        if "PARTIAL" in prop_f:
            return 0.7, "partial_furnishing_fit", ScoringReasonCode.PARTIAL_FURNISHING_MATCH.value

        return 0.4, f"furnishing_mismatch_{prop_f}_vs_{req_f}", ScoringReasonCode.OPTIONAL_DATA_MISSING.value

    def _score_availability(
        self, listing: PropertyListing, config: PropertyScoringConfig
    ) -> Tuple[float, str, str]:
        status_val = listing.availability_status
        if status_val == ListingAvailabilityStatus.AVAILABLE:
            return 1.0, "availability_confirmed", ScoringReasonCode.CONFIRMED_AVAILABLE.value
        if status_val == ListingAvailabilityStatus.CONDITIONAL:
            return 0.7, "availability_conditional", ScoringReasonCode.CONDITIONAL_AVAILABILITY.value

        # UNKNOWN, NOT_CHECKED, AWAITING_VERIFICATION
        return 0.4, f"availability_unverified_{status_val.value if hasattr(status_val, 'value') else status_val}", ScoringReasonCode.AVAILABILITY_UNVERIFIED.value

    # -----------------------------------------------------------------
    # Stale Score Management & Manual Forwarding
    # -----------------------------------------------------------------

    def check_and_mark_stale_scores(self, lead_id: uuid.UUID) -> int:
        """
        Marks matches as stale if property/listing or tenant requirements were modified.
        """
        lead = self.db.query(Lead).options(joinedload(Lead.tenant_requirement)).filter(Lead.id == lead_id).first()
        if not lead or not lead.tenant_requirement:
            return 0

        req_updated = lead.tenant_requirement.updated_at
        matches = (
            self.db.query(PropertyMatch)
            .options(joinedload(PropertyMatch.listing))
            .filter(
                PropertyMatch.lead_id == lead_id,
                PropertyMatch.match_score.isnot(None),
                PropertyMatch.is_stale.is_(False),
            )
            .all()
        )

        stale_count = 0
        for m in matches:
            reason = None
            if m.updated_at and req_updated and req_updated > m.updated_at:
                reason = "Tenant requirements updated after match was scored"
            elif m.listing and m.listing.updated_at and m.updated_at and m.listing.updated_at > m.updated_at:
                reason = "Listing attributes updated after match was scored"

            if reason:
                m.is_stale = True
                m.stale_reason = reason
                stale_count += 1

        if stale_count > 0:
            self.db.commit()

        return stale_count

    def manual_forward_candidate(
        self,
        match_id: uuid.UUID,
        target_status: PropertyMatchStatus,
        reason: str,
        actor_id: str = "system",
    ) -> PropertyMatch:
        """
        Manual workflow override: Promotes a candidate (e.g. to READY_FOR_AGENT_VERIFICATION).
        Keeps system match_score and score_breakdown unchanged for transparency.
        """
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Property match record '{match_id}' not found.",
            )

        old_status = match.match_status
        match.match_status = target_status.value
        match.manual_override = True
        match.manual_override_by = actor_id
        match.manual_override_at = datetime.now(timezone.utc)
        match.manual_override_reason = reason

        self.db.commit()
        self.db.refresh(match)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_MATCH_MANUAL_FORWARD",
                entity_type="property_match",
                entity_id=str(match.id),
                old_value={"status": old_status},
                new_value={
                    "status": target_status.value,
                    "reason": reason,
                    "actor": actor_id,
                },
            )
        )

        return match
