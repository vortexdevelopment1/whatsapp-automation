import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models.property_match import PropertyMatch
from app.models.property_listing import PropertyListing
from app.models.lead import Lead
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.enums import (
    PropertyMatchStatus,
    QualificationStatus,
    PropertyAgentOutreachStatus,
    ListingAvailabilityStatus,
    PropertyListingStatus,
)

from app.services.property_scoring_config import PropertyScoringConfig


class PropertyAgentVerificationSelectionService:
    """
    Selects eligible candidate matches for a lead that are ready for listing agent verification.
    Enforces qualification status, active listing checks, exclusion of already contacted matches,
    and top-N bounds.
    """

    def __init__(self, db: Session):
        self.db = db

    def select_eligible_matches(
        self,
        lead_id: uuid.UUID,
        max_candidates: Optional[int] = None,
    ) -> List[PropertyMatch]:
        # 1. Lead qualification check
        lead = self.db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        # Lead must have qualified tenant requirements
        from app.models.tenant_requirement import TenantRequirement
        req = self.db.query(TenantRequirement).filter(TenantRequirement.lead_id == lead.id).first()
        if not req or req.qualification_status != QualificationStatus.QUALIFIED:
            status_val = req.qualification_status.value if req and req.qualification_status else "NO_REQUIREMENT"
            raise ValueError(
                f"Lead '{lead_id}' is not in QUALIFIED status (current: {status_val}). Cannot conduct outreach."
            )


        # 2. Determine max candidates bound
        if max_candidates is None:
            scoring_config = PropertyScoringConfig.get_config()
            max_candidates = scoring_config.maximum_candidates_for_agent_verification

        # 3. Query candidate matches
        # Eligible matches must:
        # - have hard_filter_passed == True
        # - not be marked stale
        # - match_status == READY_FOR_AGENT_VERIFICATION or manual_override == True
        query = (
            self.db.query(PropertyMatch)
            .join(PropertyListing, PropertyMatch.listing_id == PropertyListing.id)
            .filter(
                PropertyMatch.lead_id == lead_id,
                PropertyMatch.hard_filter_passed.is_(True),
                PropertyMatch.is_stale.is_(False),
                PropertyListing.listing_status == PropertyListingStatus.ACTIVE,
                or_(

                    PropertyListing.availability_status.is_(None),
                    PropertyListing.availability_status != ListingAvailabilityStatus.UNAVAILABLE.value,
                ),
                or_(
                    PropertyMatch.match_status == PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value,
                    PropertyMatch.manual_override.is_(True),
                ),
            )
            .order_by(
                PropertyMatch.rank.asc().nullslast(),
                PropertyMatch.match_score.desc().nullslast(),
                PropertyMatch.created_at.asc(),
            )
        )

        all_candidates = query.all()

        # 4. Filter out matches that already have active or replied outreach
        active_statuses = [
            PropertyAgentOutreachStatus.QUEUED,
            PropertyAgentOutreachStatus.SENT,
            PropertyAgentOutreachStatus.DELIVERED,
            PropertyAgentOutreachStatus.READ,
            PropertyAgentOutreachStatus.REPLIED,
        ]

        selected: List[PropertyMatch] = []
        for match in all_candidates:
            # Check existing outreach for this match
            existing_outreach = (
                self.db.query(PropertyAgentOutreach)
                .filter(
                    PropertyAgentOutreach.property_match_id == match.id,
                    PropertyAgentOutreach.status.in_(active_statuses),
                )
                .first()
            )
            if existing_outreach:
                continue

            selected.append(match)
            if len(selected) >= max_candidates:
                break

        return selected
