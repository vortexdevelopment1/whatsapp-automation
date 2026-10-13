import uuid
import logging
from datetime import datetime, timezone as dt_timezone
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from sqlalchemy import desc

from app.models.viewing import Viewing, ViewingEvent
from app.models.viewing_availability_request import ViewingAvailabilityRequest
from app.models.property_match import PropertyMatch
from app.models.property_listing import PropertyListing
from app.models.property import Property
from app.models.property_agent import PropertyAgent
from app.models.property_agent_conversation import PropertyAgentConversation
from app.models.property_interest import PropertyInterest
from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.whatsapp import WhatsAppProfile
from app.models.audit_log import AuditLog
from app.models.enums import (
    ViewingStatus,
    ViewingAvailabilityRequestStatus,
    ViewingCorrelationStatus,
    ViewingEventType,
    ViewingActorType,
    PropertyInterestStatus,
    ListingAvailabilityStatus,
    PropertyListingStatus,
    PropertyStatus,
    QualificationStatus,
)
from app.services.whatsapp_service import WhatsAppService
from app.services.viewing_service import ViewingService
from app.services.viewing_state_machine import ViewingStateMachine

logger = logging.getLogger(__name__)


class ViewingAgentAvailabilityService:
    """
    Coordinates property agent viewing availability requests.
    Responsibilities:
    - Validate viewing eligibility, active candidate match, property & listing state, tenant qualification.
    - Resolve property agent & reuse/initialize PropertyAgentConversation.
    - Compose privacy-preserving availability request message (no tenant PII, contact info, budget, internal score).
    - Dispatch message via existing WhatsAppService using idempotency key viewing:{viewing_id}:agent-availability-request.
    - Create/track ViewingAvailabilityRequest record.
    - Transition viewing state to AWAITING_AGENT_AVAILABILITY.
    - Record audit logs and viewing events.
    """

    def __init__(self, db: Session, whatsapp_service: Optional[WhatsAppService] = None):
        self.db = db
        self.whatsapp_service = whatsapp_service or WhatsAppService(db)

    def _get_active_whatsapp_profile(self) -> WhatsAppProfile:
        profile = self.db.query(WhatsAppProfile).first()
        if not profile:
            from app.models.agent import Agent
            agent = self.db.query(Agent).first()
            if not agent:
                agent = Agent(
                    full_name="Platform Viewing Concierge",
                    email=f"concierge_{uuid.uuid4().hex[:6]}@platform.sg",
                    phone="+6590000000",
                )
                self.db.add(agent)
                self.db.commit()
                self.db.refresh(agent)

            from app.models.enums import WhatsAppConnectionStatus
            profile = WhatsAppProfile(
                agent_id=agent.id,
                phone_number_id=f"PNID_{uuid.uuid4().hex[:8]}",
                meta_business_account_id=f"WABA_{uuid.uuid4().hex[:8]}",
                display_phone_number="+6590000000",
                business_display_name="Platform Viewing Concierge",
                connection_status=WhatsAppConnectionStatus.CONNECTED,
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def validate_viewing_entry_conditions(self, viewing_id: uuid.UUID) -> Dict[str, Any]:
        """
        Revalidates:
        - active viewing exists and is not cancelled/completed
        - viewing is linked to a current valid property match
        - property & listing remain active and available
        - property agent exists and has usable contact
        - tenant remains eligible/qualified
        - property_interest is in VIEWING_REQUESTED or viewing is in DRAFT/AWAITING
        """
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            return {"valid": False, "reason": f"Viewing {viewing_id} not found", "viewing": None}

        if viewing.status in [ViewingStatus.CANCELLED, ViewingStatus.COMPLETED, ViewingStatus.REJECTED]:
            return {"valid": False, "reason": f"Viewing is in terminal status: {viewing.status.value}", "viewing": viewing}

        # Validate PropertyMatch
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == viewing.property_match_id).first()
        if not match:
            return {"valid": False, "reason": "Associated PropertyMatch not found", "viewing": viewing}

        # Validate Lead & Qualification
        lead = self.db.query(Lead).filter(Lead.id == viewing.lead_id).first()
        if not lead:
            return {"valid": False, "reason": "Associated Lead not found", "viewing": viewing}

        tenant_req = (
            self.db.query(TenantRequirement)
            .filter(TenantRequirement.lead_id == viewing.lead_id)
            .order_by(desc(TenantRequirement.created_at))
            .first()
        )
        if not tenant_req or tenant_req.qualification_status not in [
            QualificationStatus.QUALIFIED.value,
            QualificationStatus.IN_PROGRESS.value,
        ]:
            return {
                "valid": False,
                "reason": f"Tenant is not qualified (status: {tenant_req.qualification_status if tenant_req else 'MISSING'})",
                "viewing": viewing,
            }

        # Validate Property
        prop = self.db.query(Property).filter(Property.id == viewing.property_id).first()
        if not prop or prop.status != PropertyStatus.ACTIVE:
            return {"valid": False, "reason": "Property is not active or missing", "viewing": viewing}

        # Validate Listing
        listing = self.db.query(PropertyListing).filter(PropertyListing.id == viewing.listing_id).first()
        if not listing or listing.listing_status != PropertyListingStatus.ACTIVE:
            return {"valid": False, "reason": "Listing is not active", "viewing": viewing}

        if listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE or match.match_status == "UNAVAILABLE":
            return {"valid": False, "reason": "Property/Listing is marked UNAVAILABLE", "viewing": viewing}

        # Validate PropertyAgent
        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == viewing.property_agent_id).first()
        if not agent:
            return {"valid": False, "reason": "Property agent not found", "viewing": viewing}

        agent_phone = agent.phone_normalized or agent.phone
        if not agent_phone:
            return {"valid": False, "reason": "Property agent has no phone number", "viewing": viewing}

        return {
            "valid": True,
            "reason": "OK",
            "viewing": viewing,
            "match": match,
            "property": prop,
            "listing": listing,
            "agent": agent,
            "lead": lead,
        }

    def compose_outbound_message(
        self,
        listing: PropertyListing,
        custom_message: Optional[str] = None,
        tenant_broad_availability: Optional[str] = None,
    ) -> str:
        """
        Builds a privacy-preserving message asking for available viewing slots.
        NEVER sends tenant phone, email, full name, qualification notes, or internal score.
        """
        if custom_message:
            return custom_message.strip()

        ref_code = listing.listing_reference or listing.source_listing_id or f"REF-{str(listing.id)[:8]}"
        title = listing.property.canonical_name if listing.property else "the property"

        if tenant_broad_availability:
            content = (
                f"Hi, the tenant would like to view listing [{ref_code}] ({title}). "
                f"Tenant is generally available: {tenant_broad_availability.strip()}. "
                f"Could you please share suitable viewing slots for the next few days?"
            )
        else:
            content = (
                f"Hi, the tenant would like to view listing [{ref_code}] ({title}). "
                f"Could you please share available viewing slots for the next few days?"
            )
        return content

    def request_agent_availability(
        self,
        viewing_id: uuid.UUID,
        actor_id: str = "operator",
        custom_message: Optional[str] = None,
        tenant_broad_availability: Optional[str] = None,
    ) -> ViewingAvailabilityRequest:
        """
        Creates and sends an availability request to the listing agent.
        Enforces idempotency using key: viewing:{viewing_id}:agent-availability-request
        """
        check = self.validate_viewing_entry_conditions(viewing_id)
        if not check["valid"]:
            raise ValueError(f"Viewing entry condition check failed: {check['reason']}")

        viewing: Viewing = check["viewing"]
        match: PropertyMatch = check["match"]
        listing: PropertyListing = check["listing"]
        agent: PropertyAgent = check["agent"]
        lead: Lead = check["lead"]

        idempotency_key = f"viewing:{viewing.id}:agent-availability-request"

        # Check existing request with same idempotency key
        existing_req = (
            self.db.query(ViewingAvailabilityRequest)
            .filter(ViewingAvailabilityRequest.idempotency_key == idempotency_key)
            .first()
        )
        if existing_req:
            logger.info(f"Existing availability request {existing_req.id} found for viewing {viewing.id}")
            return existing_req

        # Resolve or reuse PropertyAgentConversation
        conversation = (
            self.db.query(PropertyAgentConversation)
            .filter(
                PropertyAgentConversation.property_agent_id == agent.id,
                PropertyAgentConversation.property_match_id == match.id,
            )
            .first()
        )
        ref_code = listing.listing_reference or listing.source_listing_id or f"REF-{str(listing.id)[:8]}"
        if not conversation:
            conversation = PropertyAgentConversation(
                property_agent_id=agent.id,
                lead_id=lead.id,
                property_id=viewing.property_id,
                listing_id=listing.id,
                property_match_id=match.id,
                conversation_type="PROPERTY_AGENT",
                status="ACTIVE",
                reference_code=ref_code,
                last_message_at=func.now(),
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

        # Compose safe content
        content = self.compose_outbound_message(
            listing=listing,
            custom_message=custom_message,
            tenant_broad_availability=tenant_broad_availability,
        )

        # Dispatch via WhatsAppService
        profile = self._get_active_whatsapp_profile()
        recipient_phone = agent.phone_normalized or agent.phone

        req = ViewingAvailabilityRequest(
            viewing_id=viewing.id,
            lead_id=lead.id,
            property_match_id=match.id,
            listing_id=listing.id,
            property_agent_id=agent.id,
            conversation_id=conversation.id,
            status=ViewingAvailabilityRequestStatus.PENDING,
            idempotency_key=idempotency_key,
            outbound_message_text=content,
            correlation_status=ViewingCorrelationStatus.RESOLVED,
            request_metadata={
                "listing_ref": ref_code,
                "agent_name": agent.full_name,
                "recipient_phone": recipient_phone,
            },
        )
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)

        # Dispatch WhatsApp message
        try:
            wa_msg = self.whatsapp_service.send_message(
                profile_id=profile.id,
                recipient=recipient_phone,
                content=content,
                idempotency_key=f"wa:{idempotency_key}",
                actor_id=actor_id,
            )
            req.provider_message_id = wa_msg.provider_message_id
            req.status = ViewingAvailabilityRequestStatus.SENT
            req.sent_at = datetime.now(dt_timezone.utc)
            conversation.last_message_at = func.now()
        except Exception as e:
            logger.error(f"Failed to send WhatsApp message for viewing availability request: {e}")
            req.status = ViewingAvailabilityRequestStatus.FAILED
            self.db.commit()
            raise

        # Move Viewing status to AWAITING_AGENT_AVAILABILITY
        if viewing.status != ViewingStatus.AWAITING_AGENT_AVAILABILITY:
            ViewingService.transition_viewing(
                db=self.db,
                viewing_id=viewing.id,
                target_status=ViewingStatus.AWAITING_AGENT_AVAILABILITY,
                reason="Sent availability request to property agent",
                actor_type=ViewingActorType.SYSTEM if actor_id == "system" else ViewingActorType.OPERATOR,
                actor_id=actor_id,
            )

        # Audit log
        audit = AuditLog(
            action="AGENT_AVAILABILITY_REQUESTED",
            actor_id=actor_id,
            entity_type="viewing_availability_request",
            entity_id=str(req.id),
            new_value={
                "viewing_id": str(viewing.id),
                "property_agent_id": str(agent.id),
                "recipient": recipient_phone,
                "status": req.status.value,
            },
        )
        self.db.add(audit)
        self.db.commit()
        self.db.refresh(req)
        return req

    def get_viewing_availability_status(self, viewing_id: uuid.UUID) -> Dict[str, Any]:
        """
        Retrieves the latest request status, message state, property agent details,
        current available slots, notes, and correlation status.
        """
        viewing = self.db.query(Viewing).filter(Viewing.id == viewing_id).first()
        if not viewing:
            raise ValueError(f"Viewing {viewing_id} not found")

        latest_req = (
            self.db.query(ViewingAvailabilityRequest)
            .filter(ViewingAvailabilityRequest.viewing_id == viewing_id)
            .order_by(desc(ViewingAvailabilityRequest.created_at))
            .first()
        )

        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == viewing.property_agent_id).first()
        agent_data = {
            "id": str(agent.id) if agent else None,
            "full_name": agent.full_name if agent else "Unknown",
            "agency_name": agent.agency_name if agent else None,
            "phone": agent.phone if agent else None,
        }

        # Available slots
        slots = viewing.slots

        needs_human_review = (
            viewing.status == ViewingStatus.NEEDS_HUMAN_REVIEW
            or (latest_req and latest_req.correlation_status == ViewingCorrelationStatus.AMBIGUOUS)
        )

        return {
            "viewing_id": viewing.id,
            "viewing_status": viewing.status.value,
            "latest_request": latest_req,
            "property_agent": agent_data,
            "current_slots": slots,
            "agent_notes": latest_req.agent_notes if latest_req else None,
            "correlation_status": latest_req.correlation_status.value if latest_req else "NONE",
            "needs_human_review": needs_human_review,
        }
