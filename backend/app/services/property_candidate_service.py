import uuid
from datetime import datetime, timezone, date, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException, status
from sqlalchemy.orm import Session, joinedload

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.qualification_decision import QualificationDecision
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_source import PropertySource
from app.models.property_match import PropertyMatch
from app.models.property_matching_run import PropertyMatchingRun
from app.models.enums import (
    QualificationStatus,
    PropertyStatus,
    PropertyListingStatus,
    PropertySourceStatus,
    ListingAvailabilityStatus,
    PropertyMatchStatus,
    HardFilterReasonCode,
    UnknownDataPolicy,
    MatchingRunStatus,
)
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.services.property_matching_config import PropertyMatchingConfig, DEFAULT_MATCHING_CONFIG


class PropertyCandidateService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    def run_candidate_search(
        self,
        lead_id: uuid.UUID,
        config: Optional[PropertyMatchingConfig] = None,
        actor_id: str = "system",
    ) -> PropertyMatchingRun:
        """
        Executes Module 4 Phase 3 Candidate Search and Hard Filters for a QUALIFIED tenant lead.
        """
        matching_config = config or DEFAULT_MATCHING_CONFIG

        # 1. Handoff Verification: Lead must be QUALIFIED in Module 3
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
        if not req:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Lead '{lead_id}' has no tenant requirements on record. Cannot run property matching.",
            )

        if req.qualification_status != QualificationStatus.QUALIFIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Lead '{lead_id}' is not QUALIFIED (Current status: {req.qualification_status.value}). "
                    "Property matching may only be executed for verified QUALIFIED tenant leads."
                ),
            )

        # Find latest qualification decision for reference
        latest_decision = (
            self.db.query(QualificationDecision)
            .filter(QualificationDecision.lead_id == lead_id)
            .order_by(QualificationDecision.created_at.desc())
            .first()
        )

        # 2. Build Requirement Snapshot
        requirement_snapshot = {
            "preferred_locations": req.preferred_locations or [],
            "budget_min": float(req.budget_min) if req.budget_min else None,
            "budget_max": float(req.budget_max) if req.budget_max else None,
            "currency": req.currency or "SGD",
            "property_type": req.property_type,
            "bedrooms": req.bedrooms,
            "move_in_date": req.move_in_date.isoformat() if req.move_in_date else None,
            "lease_duration_months": req.lease_duration_months,
            "furnishing": req.furnishing,
            "occupants": req.occupants,
            "completion_percentage": req.completion_percentage,
        }

        # 3. Create Matching Run Record
        matching_run = PropertyMatchingRun(
            lead_id=lead_id,
            qualification_decision_id=latest_decision.id if latest_decision else None,
            config_version=matching_config.config_version,
            status=MatchingRunStatus.RUNNING,
            requirement_snapshot=requirement_snapshot,
        )
        self.db.add(matching_run)
        self.db.commit()
        self.db.refresh(matching_run)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_MATCHING_RUN_STARTED",
                entity_type="property_matching_run",
                entity_id=str(matching_run.id),
                new_value={
                    "lead_id": str(lead_id),
                    "config_version": matching_config.config_version,
                },
            )
        )

        try:
            # 4. Database-level base candidate search
            inventory = self._query_eligible_inventory(req, matching_config)

            total_considered = len(inventory)
            eligible_count = 0
            filtered_count = 0
            needs_review_count = 0

            # 5. Apply Hard Filters
            for prop, listing, source in inventory:
                eval_result = self.evaluate_hard_filters(req, prop, listing, source, matching_config)

                # Determine Match Status
                if not eval_result["passed"]:
                    match_status = PropertyMatchStatus.FILTERED_OUT
                    filtered_count += 1
                elif eval_result.get("needs_review", False):
                    match_status = PropertyMatchStatus.NEEDS_REVIEW
                    needs_review_count += 1
                else:
                    match_status = PropertyMatchStatus.ELIGIBLE_FOR_SCORING
                    eligible_count += 1

                # 6. Upsert PropertyMatch Record
                match_record = PropertyMatch(
                    lead_id=lead_id,
                    property_id=prop.id,
                    listing_id=listing.id,
                    matching_run_id=matching_run.id,
                    match_status=match_status.value,
                    hard_filter_passed=eval_result["passed"],
                    hard_filter_result=eval_result,
                    filter_rule_version=matching_config.filter_rule_version,
                    matching_config_version=matching_config.config_version,
                    availability_status=listing.availability_status.value if listing.availability_status else "UNKNOWN",
                )
                self.db.add(match_record)

            # 7. Complete Run
            matching_run.total_inventory_considered = total_considered
            matching_run.eligible_candidates = eligible_count
            matching_run.filtered_candidates = filtered_count
            matching_run.needs_review_candidates = needs_review_count
            matching_run.status = MatchingRunStatus.COMPLETED
            matching_run.completed_at = datetime.now(timezone.utc)

            self.db.commit()
            self.db.refresh(matching_run)

            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action="PROPERTY_MATCHING_RUN_COMPLETED",
                    entity_type="property_matching_run",
                    entity_id=str(matching_run.id),
                    new_value={
                        "considered": total_considered,
                        "eligible": eligible_count,
                        "filtered_out": filtered_count,
                        "needs_review": needs_review_count,
                    },
                )
            )

            return matching_run

        except Exception as e:
            import logging
            logging.getLogger(__name__).exception("Candidate matching failed: %s", e)
            self.db.rollback()
            try:
                failed_run = self.db.query(PropertyMatchingRun).filter(PropertyMatchingRun.id == matching_run.id).first()
                if failed_run:
                    failed_run.status = MatchingRunStatus.FAILED
                    failed_run.error_message = str(e)
                    failed_run.completed_at = datetime.now(timezone.utc)
                    self.db.commit()
            except Exception:
                self.db.rollback()
            raise

    def _query_eligible_inventory(
        self,
        req: TenantRequirement,
        config: PropertyMatchingConfig,
    ) -> List[Tuple[Property, PropertyListing, PropertySource]]:
        """
        Database-level query retrieving active inventory before applying detailed in-memory hard filters.
        """
        query = (
            self.db.query(Property, PropertyListing, PropertySource)
            .join(PropertyListing, Property.id == PropertyListing.property_id)
            .join(PropertySource, PropertyListing.source_id == PropertySource.id)
            .filter(
                Property.status == PropertyStatus.ACTIVE,
                PropertyListing.listing_status == PropertyListingStatus.ACTIVE,
                PropertySource.status == PropertySourceStatus.ACTIVE,
            )
        )

        # Basic budget upper bound to optimize query (1.5x buffer)
        if req.budget_max is not None:
            tolerance_multiplier = Decimal(str(1 + (config.budget_tolerance_percent / 100.0) + 0.5))
            max_ceiling = req.budget_max * tolerance_multiplier
            query = query.filter(
                (PropertyListing.asking_price.is_(None)) | (PropertyListing.asking_price <= max_ceiling)
            )

        query = query.limit(config.max_initial_candidates)
        return query.all()

    def evaluate_hard_filters(
        self,
        req: TenantRequirement,
        prop: Property,
        listing: PropertyListing,
        source: PropertySource,
        config: PropertyMatchingConfig,
    ) -> Dict[str, Any]:
        """
        Evaluates deterministic hard filters and returns an explainable result payload.
        """
        rules_eval: List[Dict[str, Any]] = []
        failed_rules: List[str] = []
        reason_codes: List[str] = []
        needs_review: bool = False

        # -------------------------------------------------------------
        # 1. Base Inventory Eligibility & Availability
        # -------------------------------------------------------------
        if prop.status != PropertyStatus.ACTIVE:
            rules_eval.append({
                "rule": "BASE_ELIGIBILITY",
                "passed": false,
                "reason": "property_is_inactive_or_archived",
                "code": HardFilterReasonCode.PROPERTY_INACTIVE.value,
            })
            failed_rules.append("BASE_ELIGIBILITY")
            reason_codes.append(HardFilterReasonCode.PROPERTY_INACTIVE.value)

        if listing.listing_status != PropertyListingStatus.ACTIVE:
            rules_eval.append({
                "rule": "BASE_ELIGIBILITY",
                "passed": False,
                "reason": "listing_is_inactive_or_expired",
                "code": HardFilterReasonCode.LISTING_INACTIVE.value,
            })
            failed_rules.append("BASE_ELIGIBILITY")
            reason_codes.append(HardFilterReasonCode.LISTING_INACTIVE.value)

        if listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE:
            rules_eval.append({
                "rule": "AVAILABILITY",
                "passed": False,
                "reason": "listing_status_is_unavailable",
                "code": HardFilterReasonCode.LISTING_UNAVAILABLE.value,
            })
            failed_rules.append("AVAILABILITY")
            reason_codes.append(HardFilterReasonCode.LISTING_UNAVAILABLE.value)
        elif listing.availability_status in (
            ListingAvailabilityStatus.UNKNOWN,
            ListingAvailabilityStatus.NOT_CHECKED,
            ListingAvailabilityStatus.AWAITING_VERIFICATION,
        ):
            if config.allow_unknown_availability == UnknownDataPolicy.FILTER_OUT:
                rules_eval.append({
                    "rule": "AVAILABILITY",
                    "passed": False,
                    "reason": "availability_status_unknown_rejected_by_policy",
                    "code": HardFilterReasonCode.LISTING_UNAVAILABLE.value,
                })
                failed_rules.append("AVAILABILITY")
                reason_codes.append(HardFilterReasonCode.LISTING_UNAVAILABLE.value)
            elif config.allow_unknown_availability == UnknownDataPolicy.NEEDS_REVIEW:
                rules_eval.append({
                    "rule": "AVAILABILITY",
                    "passed": True,
                    "reason": "availability_unknown_marked_for_review",
                    "code": "AVAILABILITY_NEEDS_REVIEW",
                })
                needs_review = True
            else:
                rules_eval.append({
                    "rule": "AVAILABILITY",
                    "passed": True,
                    "reason": "availability_unknown_allowed_for_later_verification",
                })
        else:
            rules_eval.append({
                "rule": "AVAILABILITY",
                "passed": True,
                "reason": "listing_is_available",
            })

        # -------------------------------------------------------------
        # 2. Currency Check
        # -------------------------------------------------------------
        tenant_currency = (req.currency or "SGD").upper()
        listing_currency = (listing.currency or "SGD").upper()
        if tenant_currency != listing_currency:
            rules_eval.append({
                "rule": "CURRENCY",
                "passed": False,
                "reason": f"currency_mismatch_{tenant_currency}_vs_{listing_currency}",
                "tenant_value": tenant_currency,
                "property_value": listing_currency,
                "code": HardFilterReasonCode.CURRENCY_MISMATCH.value,
            })
            failed_rules.append("CURRENCY")
            reason_codes.append(HardFilterReasonCode.CURRENCY_MISMATCH.value)
        else:
            rules_eval.append({
                "rule": "CURRENCY",
                "passed": True,
                "reason": "currency_matches",
                "tenant_value": tenant_currency,
                "property_value": listing_currency,
            })

        # -------------------------------------------------------------
        # 3. Property Type Hard Filter
        # -------------------------------------------------------------
        if req.property_type and config.strict_property_type:
            req_type = req.property_type.strip().upper()
            prop_type = (prop.property_type.value if hasattr(prop.property_type, "value") else str(prop.property_type)).upper()

            if req_type != "ANY" and req_type != "OTHER":
                if req_type != prop_type:
                    rules_eval.append({
                        "rule": "PROPERTY_TYPE",
                        "passed": False,
                        "reason": f"property_type_mismatch_{req_type}_vs_{prop_type}",
                        "tenant_value": req_type,
                        "property_value": prop_type,
                        "code": HardFilterReasonCode.PROPERTY_TYPE_MISMATCH.value,
                    })
                    failed_rules.append("PROPERTY_TYPE")
                    reason_codes.append(HardFilterReasonCode.PROPERTY_TYPE_MISMATCH.value)
                else:
                    rules_eval.append({
                        "rule": "PROPERTY_TYPE",
                        "passed": True,
                        "reason": "exact_property_type_match",
                        "tenant_value": req_type,
                        "property_value": prop_type,
                    })

        # -------------------------------------------------------------
        # 4. Bedrooms Hard Filter
        # -------------------------------------------------------------
        if req.bedrooms is not None:
            prop_beds = prop.bedrooms
            if prop_beds is None:
                rules_eval.append({
                    "rule": "BEDROOMS",
                    "passed": False,
                    "reason": "bedrooms_unknown_on_property",
                    "code": HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value,
                })
                failed_rules.append("BEDROOMS")
                reason_codes.append(HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value)
            elif config.minimum_bedroom_strict and prop_beds < req.bedrooms:
                rules_eval.append({
                    "rule": "BEDROOMS",
                    "passed": False,
                    "reason": f"below_required_bedrooms_{prop_beds}_lt_{req.bedrooms}",
                    "tenant_value": req.bedrooms,
                    "property_value": prop_beds,
                    "code": HardFilterReasonCode.BELOW_REQUIRED_BEDROOMS.value,
                })
                failed_rules.append("BEDROOMS")
                reason_codes.append(HardFilterReasonCode.BELOW_REQUIRED_BEDROOMS.value)
            elif not config.allow_extra_bedrooms and prop_beds > req.bedrooms:
                rules_eval.append({
                    "rule": "BEDROOMS",
                    "passed": False,
                    "reason": f"exceeds_exact_bedrooms_{prop_beds}_gt_{req.bedrooms}",
                    "tenant_value": req.bedrooms,
                    "property_value": prop_beds,
                    "code": HardFilterReasonCode.BELOW_REQUIRED_BEDROOMS.value,
                })
                failed_rules.append("BEDROOMS")
                reason_codes.append(HardFilterReasonCode.BELOW_REQUIRED_BEDROOMS.value)
            else:
                rules_eval.append({
                    "rule": "BEDROOMS",
                    "passed": True,
                    "reason": "bedrooms_compatible",
                    "tenant_value": req.bedrooms,
                    "property_value": prop_beds,
                })

        # -------------------------------------------------------------
        # 5. Budget Hard Filter with Configurable Tolerance %
        # -------------------------------------------------------------
        if req.budget_max is not None:
            if listing.asking_price is None:
                if config.allow_unknown_price == UnknownDataPolicy.FILTER_OUT:
                    rules_eval.append({
                        "rule": "BUDGET",
                        "passed": False,
                        "reason": "asking_price_missing_on_listing",
                        "code": HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value,
                    })
                    failed_rules.append("BUDGET")
                    reason_codes.append(HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value)
                else:
                    rules_eval.append({
                        "rule": "BUDGET",
                        "passed": True,
                        "reason": "asking_price_unknown_marked_for_review",
                    })
                    needs_review = True
            else:
                tolerance_ratio = Decimal(str(1.0 + (config.budget_tolerance_percent / 100.0)))
                allowed_ceiling = (Decimal(str(req.budget_max)) * tolerance_ratio).quantize(Decimal("0.01"))
                asking_price = Decimal(str(listing.asking_price))

                if asking_price > allowed_ceiling:
                    rules_eval.append({
                        "rule": "BUDGET",
                        "passed": False,
                        "reason": f"asking_price_above_budget_limit_{asking_price}_gt_{allowed_ceiling}",
                        "tenant_value": float(req.budget_max),
                        "property_value": float(asking_price),
                        "tolerance_ceiling": float(allowed_ceiling),
                        "code": HardFilterReasonCode.ABOVE_BUDGET_LIMIT.value,
                    })
                    failed_rules.append("BUDGET")
                    reason_codes.append(HardFilterReasonCode.ABOVE_BUDGET_LIMIT.value)
                else:
                    rules_eval.append({
                        "rule": "BUDGET",
                        "passed": True,
                        "reason": "price_within_budget_and_tolerance",
                        "tenant_value": float(req.budget_max),
                        "property_value": float(asking_price),
                        "tolerance_ceiling": float(allowed_ceiling),
                    })

        # -------------------------------------------------------------
        # 6. Location Hard Filter
        # -------------------------------------------------------------
        if req.preferred_locations and len(req.preferred_locations) > 0:
            tenant_locs = [str(l).strip().lower() for l in req.preferred_locations if str(l).strip()]
            if tenant_locs:
                prop_location_corpus = " ".join([
                    (prop.address_normalized or "").lower(),
                    (prop.building_name or "").lower(),
                    (prop.canonical_name or "").lower(),
                    (prop.address_line_1 or "").lower(),
                    (prop.district or "").lower(),
                    (prop.city or "").lower(),
                ])

                matched_loc = None
                for loc in tenant_locs:
                    if loc in prop_location_corpus:
                        matched_loc = loc
                        break

                if not matched_loc:
                    rules_eval.append({
                        "rule": "LOCATION",
                        "passed": False,
                        "reason": "property_outside_preferred_locations",
                        "tenant_value": req.preferred_locations,
                        "property_value": prop.address_line_1,
                        "code": HardFilterReasonCode.LOCATION_OUTSIDE_ALLOWED_AREA.value,
                    })
                    failed_rules.append("LOCATION")
                    reason_codes.append(HardFilterReasonCode.LOCATION_OUTSIDE_ALLOWED_AREA.value)
                else:
                    rules_eval.append({
                        "rule": "LOCATION",
                        "passed": True,
                        "reason": f"location_matched_on_{matched_loc}",
                        "tenant_value": req.preferred_locations,
                        "matched_location": matched_loc,
                    })

        # -------------------------------------------------------------
        # 7. Move-in Date Filter with Configurable Tolerance Days
        # -------------------------------------------------------------
        if req.move_in_date:
            if listing.available_from is None:
                if config.allow_unknown_availability == UnknownDataPolicy.FILTER_OUT:
                    rules_eval.append({
                        "rule": "MOVE_IN_DATE",
                        "passed": False,
                        "reason": "available_from_date_missing",
                        "code": HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value,
                    })
                    failed_rules.append("MOVE_IN_DATE")
                    reason_codes.append(HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value)
                elif config.allow_unknown_availability == UnknownDataPolicy.NEEDS_REVIEW:
                    rules_eval.append({
                        "rule": "MOVE_IN_DATE",
                        "passed": True,
                        "reason": "available_from_date_unknown_marked_for_review",
                    })
                    needs_review = True
                else:
                    rules_eval.append({
                        "rule": "MOVE_IN_DATE",
                        "passed": True,
                        "reason": "available_from_unknown_allowed_for_verification",
                    })
            else:
                max_avail_date = req.move_in_date + timedelta(days=config.move_in_tolerance_days)
                if listing.available_from > max_avail_date:
                    rules_eval.append({
                        "rule": "MOVE_IN_DATE",
                        "passed": False,
                        "reason": f"available_too_late_{listing.available_from}_gt_{max_avail_date}",
                        "tenant_value": req.move_in_date.isoformat(),
                        "property_value": listing.available_from.isoformat(),
                        "tolerance_cutoff": max_avail_date.isoformat(),
                        "code": HardFilterReasonCode.AVAILABLE_TOO_LATE.value,
                    })
                    failed_rules.append("MOVE_IN_DATE")
                    reason_codes.append(HardFilterReasonCode.AVAILABLE_TOO_LATE.value)
                else:
                    rules_eval.append({
                        "rule": "MOVE_IN_DATE",
                        "passed": True,
                        "reason": "available_date_compatible",
                        "tenant_value": req.move_in_date.isoformat(),
                        "property_value": listing.available_from.isoformat(),
                    })

        # -------------------------------------------------------------
        # 8. Lease Duration Filter
        # -------------------------------------------------------------
        if req.lease_duration_months and config.lease_duration_strict:
            tenant_lease = req.lease_duration_months
            min_lease = listing.lease_min_months
            max_lease = listing.lease_max_months

            if min_lease is None and max_lease is None:
                if config.allow_unknown_lease == UnknownDataPolicy.FILTER_OUT:
                    rules_eval.append({
                        "rule": "LEASE_DURATION",
                        "passed": False,
                        "reason": "lease_terms_missing_on_listing",
                        "code": HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value,
                    })
                    failed_rules.append("LEASE_DURATION")
                    reason_codes.append(HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value)
                elif config.allow_unknown_lease == UnknownDataPolicy.NEEDS_REVIEW:
                    rules_eval.append({
                        "rule": "LEASE_DURATION",
                        "passed": True,
                        "reason": "lease_terms_unknown_marked_for_review",
                    })
                    needs_review = True
                else:
                    rules_eval.append({
                        "rule": "LEASE_DURATION",
                        "passed": True,
                        "reason": "lease_unknown_allowed_for_verification",
                    })
            else:
                incompatible = False
                if min_lease is not None and tenant_lease < min_lease:
                    incompatible = True
                if max_lease is not None and tenant_lease > max_lease:
                    incompatible = True

                if incompatible:
                    rules_eval.append({
                        "rule": "LEASE_DURATION",
                        "passed": False,
                        "reason": f"lease_term_incompatible_{tenant_lease}m_vs_bounds_{min_lease}-{max_lease}m",
                        "tenant_value": tenant_lease,
                        "property_value": f"{min_lease or 'None'}-{max_lease or 'None'}",
                        "code": HardFilterReasonCode.LEASE_TERM_INCOMPATIBLE.value,
                    })
                    failed_rules.append("LEASE_DURATION")
                    reason_codes.append(HardFilterReasonCode.LEASE_TERM_INCOMPATIBLE.value)
                else:
                    rules_eval.append({
                        "rule": "LEASE_DURATION",
                        "passed": True,
                        "reason": "lease_duration_compatible",
                        "tenant_value": tenant_lease,
                        "property_value": f"{min_lease}-{max_lease}",
                    })

        # -------------------------------------------------------------
        # 9. Furnishing Filter
        # -------------------------------------------------------------
        if req.furnishing and config.strict_furnishing:
            tenant_furn = req.furnishing.strip().upper()
            prop_furn = (prop.furnishing.value if hasattr(prop.furnishing, "value") else str(prop.furnishing)).upper()

            if tenant_furn != "FLEXIBLE" and tenant_furn != "UNKNOWN":
                if prop_furn == "UNKNOWN":
                    if config.allow_unknown_furnishing == UnknownDataPolicy.FILTER_OUT:
                        rules_eval.append({
                            "rule": "FURNISHING",
                            "passed": False,
                            "reason": "furnishing_unknown_on_property",
                            "code": HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value,
                        })
                        failed_rules.append("FURNISHING")
                        reason_codes.append(HardFilterReasonCode.UNKNOWN_REQUIRED_DATA.value)
                    else:
                        rules_eval.append({
                            "rule": "FURNISHING",
                            "passed": True,
                            "reason": "furnishing_unknown_allowed",
                        })
                elif tenant_furn != prop_furn:
                    rules_eval.append({
                        "rule": "FURNISHING",
                        "passed": False,
                        "reason": f"furnishing_mismatch_{tenant_furn}_vs_{prop_furn}",
                        "tenant_value": tenant_furn,
                        "property_value": prop_furn,
                        "code": HardFilterReasonCode.FURNISHING_MISMATCH.value,
                    })
                    failed_rules.append("FURNISHING")
                    reason_codes.append(HardFilterReasonCode.FURNISHING_MISMATCH.value)
                else:
                    rules_eval.append({
                        "rule": "FURNISHING",
                        "passed": True,
                        "reason": "furnishing_matched",
                        "tenant_value": tenant_furn,
                        "property_value": prop_furn,
                    })

        passed_all = len(failed_rules) == 0

        return {
            "passed": passed_all,
            "needs_review": needs_review if passed_all else False,
            "rules": rules_eval,
            "failed_rules": failed_rules,
            "reason_codes": reason_codes,
        }

    def manual_override_candidate(
        self,
        match_id: uuid.UUID,
        target_status: PropertyMatchStatus,
        reason: str,
        actor_id: str = "system",
    ) -> PropertyMatch:
        """
        Allows an authorized operator to override a hard-filtered candidate.
        Preserves system evaluation result intact.
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
                action="PROPERTY_MATCH_MANUAL_OVERRIDE",
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
