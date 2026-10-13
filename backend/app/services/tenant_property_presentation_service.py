"""
Tenant Property Presentation Service - Module 5 Phase 2
Coordinates loading the READY shortlist, creating tenant-safe property summaries,
dispatching WhatsApp presentations, and recording property interests.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional, Tuple, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.enums import (
    LeadStatus,
    ContactEligibility,
    OptOutStatus,
    QualificationStatus,
    QualificationMode,
    PropertyShortlistStatus,
    PropertyInterestStatus,
    PropertyPresentationMode,
)
from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
from app.models.property_match import PropertyMatch
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_interest import PropertyInterest
from app.models.whatsapp import WhatsAppProfile
from app.models.audit_log import AuditLog
from app.schemas.property_interest import (
    TenantSafePropertySummary,
    PropertyInterestResponse,
    PropertyPresentationResult,
)
from app.services.presentation_config import presentation_config, PresentationConfig
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class TenantPropertyPresentationService:
    """
    Authoritative service governing tenant-facing property presentations.
    Enforces qualification gating, shortlist readiness, tenant-safe representations,
    duplicate prevention, and audit traceability.
    """

    @classmethod
    def validate_lead_and_shortlist(
        cls,
        db: Session,
        lead_id: uuid.UUID,
    ) -> Tuple[Lead, PropertyShortlist]:
        """
        Ensures tenant is eligible and shortlist is in READY status.
        Raises ValueError with clear explanation if presentation is blocked.
        """
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        # 1. Opt-out check
        if getattr(lead, "opt_out_status", None) == OptOutStatus.OPTED_OUT:
            raise ValueError("Tenant has opted out of automated communications.")

        # 2. Contact eligibility check
        if getattr(lead, "contact_eligibility", None) == ContactEligibility.INELIGIBLE:
            raise ValueError("Tenant is marked as ineligible for contact.")

        # 3. Qualification check (lead status or requirement status)
        req = db.query(TenantRequirement).filter(TenantRequirement.lead_id == lead_id).first()
        is_qualified = False
        if req and req.qualification_status:
            q_val = req.qualification_status.value if hasattr(req.qualification_status, "value") else str(req.qualification_status)
            is_qualified = q_val in ("QUALIFIED", "QUALIFICATION_COMPLETE")
        if not is_qualified and getattr(lead, "status", None):
            lead_val = lead.status.value if hasattr(lead.status, "value") else str(lead.status)
            is_qualified = lead_val in ("QUALIFIED", "QUALIFICATION_COMPLETE")

        if not is_qualified:
            raise ValueError(
                f"Lead '{lead_id}' is not in QUALIFIED status. Property presentation blocked."
            )

        # 4. Human takeover / AI paused check
        if req:
            if getattr(req, "ai_paused", False):
                raise ValueError("AI automation is currently paused for this tenant.")
            if getattr(req, "qualification_mode", None) == QualificationMode.HUMAN_REVIEW:
                raise ValueError("Tenant conversation is in HUMAN_TAKEOVER mode. Automated presentation blocked.")

        # 5. Shortlist readiness check
        shortlist = (
            db.query(PropertyShortlist)
            .filter(PropertyShortlist.lead_id == lead_id)
            .order_by(PropertyShortlist.version.desc())
            .first()
        )
        if not shortlist:
            raise ValueError(f"No property shortlist found for lead '{lead_id}'.")

        if shortlist.status != PropertyShortlistStatus.READY.value and shortlist.status != "READY":
            raise ValueError(
                f"Property shortlist '{shortlist.id}' is in status '{shortlist.status}', expected READY."
            )

        if not shortlist.items:
            raise ValueError(f"Property shortlist '{shortlist.id}' contains no candidate items.")

        return lead, shortlist

    @classmethod
    def format_tenant_safe_summary(cls, match: PropertyMatch) -> TenantSafePropertySummary:
        """
        Builds a privacy-safe, client-friendly property summary.
        STRICTLY EXCLUDES internal match scores, agent private phone, and verification logs.
        """
        prop: Optional[Property] = match.property
        listing: Optional[PropertyListing] = match.listing

        name = (
            (prop.canonical_name if prop else None)
            or (prop.building_name if prop else None)
            or (f"Condo in {prop.district}" if prop and prop.district else "Shortlisted Property")
        )
        building = prop.building_name if prop else None
        address = (prop.address_normalized or prop.address_line_1) if prop else None
        district = prop.district if prop else None
        prop_type = (
            prop.property_type.value if prop and hasattr(prop.property_type, "value") else "Condo"
        )
        bedrooms = prop.bedrooms if prop else None
        furnishing = (
            prop.furnishing.value if prop and hasattr(prop.furnishing, "value") else "Unspecified"
        )

        asking_price = float(listing.asking_price) if listing and listing.asking_price is not None else None
        currency = listing.currency if listing and listing.currency else "SGD"
        available_from = str(listing.available_from) if listing and listing.available_from else "Immediate"
        lease_min = listing.lease_min_months if listing else 12
        source_url = listing.source_url if listing else None

        # Build clean summary text
        summary_lines = [
            f"🏠 *{name}*",
            f"📍 {address or district or 'Singapore'}",
            f"💰 Rent: {currency} {asking_price:,.0f}/month" if asking_price else "💰 Rent: Price upon inquiry",
            f"🛏️ {bedrooms or '—'} Bedrooms · {prop_type} · {furnishing.replace('_', ' ').title()}",
            f"📅 Available: {available_from} (Min lease: {lease_min} months)",
        ]
        if source_url:
            summary_lines.append(f"🔗 Listing details: {source_url}")

        summary_text = "\n".join(summary_lines)

        return TenantSafePropertySummary(
            property_match_id=match.id,
            property_id=match.property_id,
            listing_id=match.listing_id or uuid.uuid4(),
            name=name,
            building_name=building,
            address=address,
            district=district,
            property_type=prop_type,
            bedrooms=bedrooms,
            furnishing=furnishing,
            asking_price=asking_price,
            currency=currency,
            available_from=available_from,
            lease_min_months=lease_min,
            source_url=source_url,
            summary_text=summary_text,
        )

    @classmethod
    def build_presentation_message_text(
        cls,
        summary: TenantSafePropertySummary,
        position: int = 1,
        total: int = 1,
    ) -> str:
        """
        Formats a clean, conversational WhatsApp message with options.
        """
        prefix = f"Here is property {position} of {total} from your curated shortlist:\n\n"
        footer = (
            "\n\nWould you like to:\n"
            "1️⃣ *Schedule a viewing*\n"
            "2️⃣ *See more details*\n"
            "3️⃣ *Show next property*\n\n"
            "You can reply with your choice, or ask any questions about this home!"
        )
        return prefix + summary.summary_text + footer

    @classmethod
    def present_single_match(
        cls,
        db: Session,
        match_id: uuid.UUID,
        actor_id: str = "operator",
        force_re_present: bool = False,
    ) -> PropertyInterest:
        """
        Presents a specific shortlisted property candidate to the tenant.
        Idempotent: does not duplicate presentation if already PRESENTED unless force_re_present is True.
        """
        match = db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise ValueError(f"PropertyMatch '{match_id}' not found.")

        # 1. Validate lead and shortlist readiness
        lead, shortlist = cls.validate_lead_and_shortlist(db, match.lead_id)

        # 2. Check candidate validity (not UNAVAILABLE or stale)
        if match.is_stale:
            raise ValueError(f"PropertyMatch '{match_id}' is stale ({match.stale_reason}).")

        if match.availability_status == "UNAVAILABLE" or (
            match.listing and getattr(match.listing, "availability_status", None) == "UNAVAILABLE"
        ):
            raise ValueError(f"PropertyMatch '{match_id}' is no longer available.")

        # Find shortlist item
        item = (
            db.query(PropertyShortlistItem)
            .filter(
                PropertyShortlistItem.shortlist_id == shortlist.id,
                PropertyShortlistItem.property_match_id == match_id,
            )
            .first()
        )

        # 3. Check existing interest record
        interest = (
            db.query(PropertyInterest)
            .filter(
                PropertyInterest.lead_id == lead.id,
                PropertyInterest.property_match_id == match_id,
            )
            .first()
        )

        if interest and interest.status == PropertyInterestStatus.PRESENTED and not force_re_present:
            logger.info(f"PropertyMatch '{match_id}' already presented to lead '{lead.id}'.")
            return interest

        # 4. Prepare tenant-safe summary and message
        summary = cls.format_tenant_safe_summary(match)
        pos = item.position if item else 1
        total = len(shortlist.items)
        msg_text = cls.build_presentation_message_text(summary, position=pos, total=total)

        # 5. Determine WhatsApp profile to send from
        profile = None
        if getattr(lead, "assigned_whatsapp_profile_id", None):
            profile = db.query(WhatsAppProfile).filter(
                WhatsAppProfile.id == lead.assigned_whatsapp_profile_id
            ).first()

        if not profile and getattr(lead, "assigned_agent_id", None):
            profile = db.query(WhatsAppProfile).filter(
                WhatsAppProfile.agent_id == lead.assigned_agent_id
            ).first()

        if not profile:
            profile = db.query(WhatsAppProfile).first()

        if not profile:
            raise ValueError("No WhatsAppProfile configured for outbound property presentation.")

        # 6. Dispatch message via WhatsAppService idempotently
        idempotency_key = f"prop-pres:{lead.id}:{shortlist.id}:{match_id}:{pos}"
        ws = WhatsAppService(db)
        sent_msg = ws.send_message(
            profile_id=profile.id,
            recipient=lead.phone,
            content=msg_text,
            idempotency_key=idempotency_key,
            actor_id=actor_id,
        )

        # 7. Create or update PropertyInterest record
        now = datetime.now(timezone.utc)
        asking_price = (
            match.listing.asking_price if match.listing and match.listing.asking_price is not None else None
        )
        avail = (
            str(match.listing.available_from)
            if match.listing and match.listing.available_from
            else (match.availability_status or "AVAILABLE")
        )

        if not interest:
            interest = PropertyInterest(
                lead_id=lead.id,
                property_match_id=match.id,
                shortlist_id=shortlist.id,
                shortlist_item_id=item.id if item else None,
                status=PropertyInterestStatus.PRESENTED,
                source_message_id=sent_msg.id,
                presented_at=now,
                presented_price=asking_price,
                presented_currency=match.listing.currency if match.listing else "SGD",
                presented_availability=avail,
                presentation_notes=f"Presented position #{pos} from shortlist v{shortlist.version}",
            )
            db.add(interest)
        else:
            interest.status = PropertyInterestStatus.PRESENTED
            interest.presented_at = now
            interest.source_message_id = sent_msg.id
            interest.presented_price = asking_price
            interest.presented_availability = avail
            interest.presentation_notes = f"Re-presented position #{pos} from shortlist v{shortlist.version}"

        db.commit()
        db.refresh(interest)

        # 8. Record audit log
        audit = AuditLog(
            actor_id=actor_id,
            action="PROPERTY_PRESENTED_TO_TENANT",
            entity_type="PropertyInterest",
            entity_id=str(interest.id),
            new_value={
                "lead_id": str(lead.id),
                "property_match_id": str(match.id),
                "shortlist_id": str(shortlist.id),
                "message_id": str(sent_msg.id),
                "position": pos,
            },
        )
        db.add(audit)
        db.commit()

        logger.info(f"Presented PropertyMatch '{match_id}' to Lead '{lead.id}' (Interest ID: {interest.id}).")
        return interest

    @classmethod
    def present_shortlist(
        cls,
        db: Session,
        lead_id: uuid.UUID,
        actor_id: str = "operator",
        mode: Optional[PropertyPresentationMode] = None,
    ) -> PropertyPresentationResult:
        """
        Presents the current shortlist to the tenant according to the presentation strategy.
        In SEQUENTIAL mode (default), presents the next unpresented property in the shortlist.
        """
        lead, shortlist = cls.validate_lead_and_shortlist(db, lead_id)
        effective_mode = mode or presentation_config.mode

        # Check existing interests to identify next unpresented item
        existing_interests = {
            i.property_match_id: i
            for i in db.query(PropertyInterest).filter(PropertyInterest.lead_id == lead_id).all()
        }

        # Filter items that are active and not unavailable
        valid_items: List[PropertyShortlistItem] = []
        for item in shortlist.items:
            m = item.property_match
            if m and not m.is_stale and m.availability_status != "UNAVAILABLE":
                valid_items.append(item)

        if not valid_items:
            raise ValueError(f"No valid, available properties found in shortlist '{shortlist.id}'.")

        presented_interests: List[PropertyInterest] = []

        if effective_mode == PropertyPresentationMode.SEQUENTIAL:
            # Pick first item that has NOT been presented yet
            target_item = None
            for it in valid_items:
                interest = existing_interests.get(it.property_match_id)
                if not interest or interest.status == PropertyInterestStatus.NOT_PRESENTED:
                    target_item = it
                    break

            # If all have been presented once, re-present the top-ranked item
            if not target_item:
                target_item = valid_items[0]

            pi = cls.present_single_match(
                db=db,
                match_id=target_item.property_match_id,
                actor_id=actor_id,
                force_re_present=True,
            )
            presented_interests.append(pi)

        elif effective_mode == PropertyPresentationMode.BATCH:
            batch_limit = presentation_config.max_properties_per_batch
            for it in valid_items[:batch_limit]:
                pi = cls.present_single_match(
                    db=db,
                    match_id=it.property_match_id,
                    actor_id=actor_id,
                )
                presented_interests.append(pi)

        responses: List[PropertyInterestResponse] = []
        for pi in presented_interests:
            resp = PropertyInterestResponse.model_validate(pi)
            if pi.property_match:
                resp.property_summary = cls.format_tenant_safe_summary(pi.property_match)
            responses.append(resp)

        return PropertyPresentationResult(
            success=True,
            lead_id=lead_id,
            presented_count=len(presented_interests),
            items=responses,
            message_sent=len(presented_interests) > 0,
            message_id=str(presented_interests[0].source_message_id) if presented_interests else None,
            note=f"Presented {len(presented_interests)} property item(s) via {effective_mode.value} mode",
        )

    @classmethod
    def list_interests_for_lead(
        cls,
        db: Session,
        lead_id: uuid.UUID,
    ) -> List[PropertyInterestResponse]:
        """
        Retrieves all property interest records for a lead with attached safe property summaries.
        """
        records = (
            db.query(PropertyInterest)
            .filter(PropertyInterest.lead_id == lead_id)
            .order_by(PropertyInterest.created_at.asc())
            .all()
        )
        results = []
        for r in records:
            resp = PropertyInterestResponse.model_validate(r)
            if r.property_match:
                resp.property_summary = cls.format_tenant_safe_summary(r.property_match)
            results.append(resp)
        return results

    @classmethod
    def update_interest_status_manual(
        cls,
        db: Session,
        interest_id: uuid.UUID,
        new_status: PropertyInterestStatus,
        tenant_notes: Optional[str] = None,
        actor_id: str = "operator",
    ) -> PropertyInterest:
        """
        Allows an authorized operator to manually record or correct tenant interest with full audit.
        """
        interest = db.query(PropertyInterest).filter(PropertyInterest.id == interest_id).first()
        if not interest:
            raise ValueError(f"PropertyInterest '{interest_id}' not found.")

        old_status = interest.status.value if hasattr(interest.status, "value") else str(interest.status)
        interest.status = new_status
        if tenant_notes:
            interest.tenant_notes = tenant_notes
        interest.responded_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(interest)

        audit = AuditLog(
            actor_id=actor_id,
            action="PROPERTY_INTEREST_MANUALLY_UPDATED",
            entity_type="PropertyInterest",
            entity_id=str(interest.id),
            old_value={"status": old_status},
            new_value={"status": new_status.value, "tenant_notes": tenant_notes},
        )
        db.add(audit)
        db.commit()

        return interest
