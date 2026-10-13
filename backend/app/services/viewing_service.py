from datetime import datetime, timezone as dt_timezone
from typing import List, Optional, Dict, Any
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.models.viewing import Viewing, ViewingSlot, ViewingEvent
from app.models.property_match import PropertyMatch
from app.models.lead import Lead
from app.models.property import Property
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.property_shortlist import PropertyShortlist, PropertyShortlistItem
from app.models.tenant_requirement import TenantRequirement
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingConfirmationStatus,
    ViewingLocationType,
    ViewingEventType,
    ViewingActorType,
    ViewingSlotStatus,
    ListingAvailabilityStatus,
    PropertyListingStatus,
    PropertyStatus,
    PropertyShortlistStatus,
    QualificationStatus,
)
from app.services.viewing_config import ViewingConfig
from app.services.viewing_state_machine import ViewingStateMachine
from app.services.viewing_slot_service import ViewingSlotService


class ViewingService:
    @classmethod
    def create_viewing_from_match(
        cls,
        db: Session,
        match_id: uuid.UUID,
        created_by: str = "operator",
        duration_minutes: Optional[int] = None,
        timezone: Optional[str] = None,
        location_type: Optional[ViewingLocationType] = None,
        location_text: Optional[str] = None,
        meeting_url: Optional[str] = None,
    ) -> Viewing:
        """
        Creates a new viewing workflow bound strictly to a qualified lead,
        active shortlisted property candidate, listing, and listing agent.
        Enforces idempotency and prevents duplicate active workflows for the same match.
        """
        match = db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise ValueError(f"PropertyMatch {match_id} not found")

        # 1. Verify Lead Status
        lead = db.query(Lead).filter(Lead.id == match.lead_id).first()
        if not lead:
            raise ValueError(f"Lead {match.lead_id} not found")

        tenant_req = (
            db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == match.lead_id)
            .order_by(desc(TenantRequirement.created_at))
            .first()
        )
        if not tenant_req or tenant_req.qualification_status != QualificationStatus.QUALIFIED.value:
            raise ValueError(
                f"Tenant {match.lead_id} is not QUALIFIED (status: {tenant_req.qualification_status if tenant_req else 'UNKNOWN'}). Viewing creation blocked."
            )

        # 2. Verify Property and Listing Active & Available
        prop = db.query(Property).filter(Property.id == match.property_id).first()
        if not prop or prop.status != PropertyStatus.ACTIVE:
            raise ValueError(f"Property {match.property_id} is inactive or not found")

        listing = db.query(PropertyListing).filter(PropertyListing.id == match.listing_id).first()
        if not listing or listing.listing_status != PropertyListingStatus.ACTIVE:
            raise ValueError(f"Listing {match.listing_id} is not active")

        if (
            listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE
            or match.availability_status == ListingAvailabilityStatus.UNAVAILABLE.value
            or match.match_status == "UNAVAILABLE"
        ):
            raise ValueError(
                f"Candidate listing {match.listing_id} is marked UNAVAILABLE. Viewing creation blocked."
            )

        # 3. Verify Property Agent Exists
        agent_id = listing.agent_id
        if not agent_id:
            raise ValueError(f"Listing {match.listing_id} has no assigned property agent")

        # 4. Check Shortlist Validity (if shortlist exists, must not be STALE)
        shortlist = (
            db.query(PropertyShortlist)
            .filter(PropertyShortlist.lead_id == match.lead_id)
            .order_by(desc(PropertyShortlist.version))
            .first()
        )
        shortlist_id = None
        shortlist_item_id = None
        if shortlist:
            if shortlist.status == PropertyShortlistStatus.STALE.value:
                raise ValueError(
                    f"Property shortlist for lead {match.lead_id} is STALE. Please refresh shortlist before creating viewing."
                )
            shortlist_id = shortlist.id
            s_item = (
                db.query(PropertyShortlistItem)
                .filter(
                    PropertyShortlistItem.shortlist_id == shortlist.id,
                    PropertyShortlistItem.property_match_id == match.id,
                )
                .first()
            )
            if s_item:
                shortlist_item_id = s_item.id

        # 5. Prevent Duplicate Active Viewing for same lead and property match (Idempotency)
        existing_active = (
            db.query(Viewing)
            .filter(
                Viewing.lead_id == match.lead_id,
                Viewing.property_match_id == match.id,
                Viewing.status.notin_([
                    ViewingStatus.CANCELLED,
                    ViewingStatus.COMPLETED,
                    ViewingStatus.REJECTED,
                ]),
            )
            .first()
        )
        if existing_active:
            # Return existing active viewing idempotently
            return existing_active

        # 6. Apply configurations
        final_timezone = timezone or ViewingConfig.DEFAULT_TIMEZONE
        ViewingSlotService.validate_timezone(final_timezone)
        final_duration = duration_minutes or ViewingConfig.DEFAULT_VIEWING_DURATION_MINUTES
        final_loc_type = location_type or ViewingLocationType.IN_PERSON
        final_loc_text = location_text or (prop.address_normalized or prop.canonical_name or "Unit Address")

        viewing = Viewing(
            lead_id=match.lead_id,
            shortlist_id=shortlist_id,
            shortlist_item_id=shortlist_item_id,
            property_match_id=match.id,
            property_id=match.property_id,
            listing_id=match.listing_id,
            property_agent_id=agent_id,
            status=ViewingStatus.DRAFT,
            timezone=final_timezone,
            duration_minutes=final_duration,
            location_type=final_loc_type,
            location_text=final_loc_text,
            meeting_url=meeting_url,
            tenant_confirmation_status=ViewingConfirmationStatus.NOT_REQUIRED,
            agent_confirmation_status=ViewingConfirmationStatus.NOT_REQUIRED,
            created_by=created_by,
        )
        db.add(viewing)
        db.flush()

        # Audit event
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.VIEWING_CREATED,
            old_status=None,
            new_status=ViewingStatus.DRAFT.value,
            actor_type=ViewingActorType.OPERATOR,
            actor_id=created_by,
            event_metadata={
                "lead_id": str(match.lead_id),
                "property_match_id": str(match.id),
                "property_id": str(match.property_id),
                "listing_id": str(match.listing_id),
                "agent_id": str(agent_id),
            },
        )
        db.add(event)

        # AuditLog
        audit = AuditLog(
            action="VIEWING_CREATED",
            actor_id=created_by,
            entity_type="viewing",
            entity_id=str(viewing.id),
            new_value={
                "property_match_id": str(match.id),
                "property_id": str(match.property_id),
                "listing_id": str(match.listing_id),
            },
        )
        db.add(audit)

        db.commit()
        db.refresh(viewing)
        return viewing

    @classmethod
    def get_viewing(cls, db: Session, viewing_id: uuid.UUID) -> Viewing:
        viewing = db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")
        return viewing

    @classmethod
    def list_viewings(
        cls,
        db: Session,
        lead_id: Optional[uuid.UUID] = None,
        status: Optional[ViewingStatus] = None,
        property_id: Optional[uuid.UUID] = None,
        property_agent_id: Optional[uuid.UUID] = None,
        upcoming_only: bool = False,
    ) -> List[Viewing]:
        query = db.query(Viewing)
        if lead_id:
            query = query.filter(Viewing.lead_id == lead_id)
        if status:
            query = query.filter(Viewing.status == status)
        if property_id:
            query = query.filter(Viewing.property_id == property_id)
        if property_agent_id:
            query = query.filter(Viewing.property_agent_id == property_agent_id)
        if upcoming_only:
            now = datetime.now(dt_timezone.utc)
            query = query.filter(
                Viewing.scheduled_start_at >= now,
                Viewing.status.in_([ViewingStatus.CONFIRMED, ViewingStatus.SLOT_PROPOSED]),
            )
        return query.order_by(desc(Viewing.created_at)).all()

    @classmethod
    def update_viewing_metadata(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        duration_minutes: Optional[int] = None,
        timezone: Optional[str] = None,
        location_type: Optional[ViewingLocationType] = None,
        location_text: Optional[str] = None,
        meeting_url: Optional[str] = None,
        outcome_notes: Optional[str] = None,
        actor_id: str = "operator",
    ) -> Viewing:
        viewing = cls.get_viewing(db, viewing_id)
        if duration_minutes is not None:
            viewing.duration_minutes = duration_minutes
        if timezone is not None:
            ViewingSlotService.validate_timezone(timezone)
            viewing.timezone = timezone
        if location_type is not None:
            viewing.location_type = location_type
        if location_text is not None:
            viewing.location_text = location_text
        if meeting_url is not None:
            viewing.meeting_url = meeting_url
        if outcome_notes is not None:
            viewing.outcome_notes = outcome_notes

        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.METADATA_UPDATED,
            old_status=viewing.status.value,
            new_status=viewing.status.value,
            actor_type=ViewingActorType.OPERATOR,
            actor_id=actor_id,
            event_metadata={"updated_fields": "metadata"},
        )
        db.add(event)
        db.commit()
        db.refresh(viewing)
        return viewing

    @classmethod
    def transition_viewing(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        target_status: ViewingStatus,
        reason: Optional[str] = None,
        actor_type: ViewingActorType = ViewingActorType.OPERATOR,
        actor_id: str = "operator",
    ) -> Viewing:
        """
        Executes a controlled state transition validated by ViewingStateMachine.
        """
        viewing = cls.get_viewing(db, viewing_id)
        old_status = viewing.status

        # Validate transition
        ViewingStateMachine.validate_transition(old_status, target_status)

        # Invariant checks for specific target states
        if target_status == ViewingStatus.CONFIRMED:
            if not viewing.scheduled_start_at:
                raise ValueError("Cannot transition viewing to CONFIRMED without a scheduled start time")
            viewing.tenant_confirmation_status = ViewingConfirmationStatus.CONFIRMED
            viewing.agent_confirmation_status = ViewingConfirmationStatus.CONFIRMED

        elif target_status == ViewingStatus.CANCELLED:
            viewing.cancelled_at = datetime.now(dt_timezone.utc)
            viewing.cancelled_by = actor_id
            viewing.cancellation_reason = reason or "Operator cancelled"
            # Cancel active slots
            for s in viewing.slots:
                if s.status in [ViewingSlotStatus.SELECTED, ViewingSlotStatus.AVAILABLE]:
                    s.status = ViewingSlotStatus.CANCELLED

        elif target_status == ViewingStatus.COMPLETED:
            viewing.completed_at = datetime.now(dt_timezone.utc)

        elif target_status == ViewingStatus.RESCHEDULE_REQUESTED:
            viewing.reschedule_count += 1
            viewing.previous_scheduled_start_at = viewing.scheduled_start_at
            viewing.previous_scheduled_end_at = viewing.scheduled_end_at
            viewing.reschedule_reason = reason

        viewing.status = target_status

        # Event audit
        event = ViewingEvent(
            viewing_id=viewing.id,
            event_type=ViewingEventType.STATUS_CHANGED,
            old_status=old_status.value,
            new_status=target_status.value,
            actor_type=actor_type,
            actor_id=actor_id,
            event_metadata={"reason": reason} if reason else None,
        )
        db.add(event)

        audit = AuditLog(
            action=f"VIEWING_STATUS_CHANGED_{target_status.value}",
            actor_id=actor_id,
            entity_type="viewing",
            entity_id=str(viewing.id),
            old_value={"status": old_status.value},
            new_value={"status": target_status.value, "reason": reason},
        )
        db.add(audit)

        db.commit()
        db.refresh(viewing)
        return viewing

    @classmethod
    def cancel_viewing(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        reason: str,
        cancelled_by: str = "OPERATOR",
    ) -> Viewing:
        return cls.transition_viewing(
            db=db,
            viewing_id=viewing_id,
            target_status=ViewingStatus.CANCELLED,
            reason=reason,
            actor_type=ViewingActorType.OPERATOR,
            actor_id=cancelled_by,
        )

    @classmethod
    def complete_viewing(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        notes: Optional[str] = None,
        actor_id: str = "operator",
    ) -> Viewing:
        viewing = cls.get_viewing(db, viewing_id)
        if notes:
            viewing.outcome_notes = notes
        return cls.transition_viewing(
            db=db,
            viewing_id=viewing_id,
            target_status=ViewingStatus.COMPLETED,
            reason=notes,
            actor_type=ViewingActorType.OPERATOR,
            actor_id=actor_id,
        )

    @classmethod
    def record_no_show(
        cls,
        db: Session,
        viewing_id: uuid.UUID,
        actor: str = "TENANT",
        notes: Optional[str] = None,
        actor_id: str = "operator",
    ) -> Viewing:
        viewing = cls.get_viewing(db, viewing_id)
        if notes:
            viewing.outcome_notes = f"No show by {actor}. Notes: {notes}"
        return cls.transition_viewing(
            db=db,
            viewing_id=viewing_id,
            target_status=ViewingStatus.NO_SHOW,
            reason=f"No show: {actor}",
            actor_type=ViewingActorType.OPERATOR,
            actor_id=actor_id,
        )
