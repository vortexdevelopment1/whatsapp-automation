import uuid
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.sql import func
from datetime import datetime

from app.models.property_match import PropertyMatch
from app.models.property_listing import PropertyListing
from app.models.property import Property
from app.models.property_agent import PropertyAgent
from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.whatsapp import WhatsAppProfile
from app.models.message import WhatsAppMessage
from app.models.template import MessageTemplate
from app.models.property_agent_conversation import PropertyAgentConversation
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.enums import (
    PropertyMatchStatus,
    QualificationStatus,
    PropertyAgentOutreachType,
    PropertyAgentOutreachStatus,
    AgentMappingStatus,
    ListingAvailabilityStatus,
)
from app.schemas.property_agent_outreach import (
    PropertyAgentMappingResult,
    OutreachMessagePreview,
    PropertyAgentOutreachResponse,
    BulkAgentOutreachRunResponse,
)
from app.schemas.audit import AuditLogCreate
from app.repositories.audit_repo import AuditRepository
from app.services.property_agent_mapping_service import PropertyAgentMappingService
from app.services.property_agent_verification_selection_service import PropertyAgentVerificationSelectionService
from app.services.whatsapp_service import WhatsAppService


class PropertyAgentOutreachService:
    """
    Coordinates listing agent resolution, message preparation with data minimization,
    dispatch via WhatsAppService, idempotency, delivery tracking, and match status progression.
    """

    def __init__(self, db: Session):
        self.db = db
        self.mapping_service = PropertyAgentMappingService(db)
        self.selection_service = PropertyAgentVerificationSelectionService(db)
        self.whatsapp_service = WhatsAppService(db)
        self.audit_repo = AuditRepository(db)

    def _get_active_whatsapp_profile(self) -> WhatsAppProfile:
        profile = self.db.query(WhatsAppProfile).first()
        if not profile:
            from app.models.agent import Agent
            agent = self.db.query(Agent).first()
            if not agent:
                agent = Agent(
                    full_name="Platform Concierge Agent",
                    email=f"concierge_{uuid.uuid4().hex[:6]}@platform.sg",
                    phone="+6590000000",
                    agency_name="Platform Property",
                    registration_number="R000001A",
                )
                self.db.add(agent)
                self.db.commit()
                self.db.refresh(agent)

            profile = WhatsAppProfile(
                agent_id=agent.id,
                phone_number_id="pn_platform_default",
                display_phone_number="+6590000000",
                business_display_name="Platform Property Concierge",
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile


    def _build_context_and_content(
        self,
        match: PropertyMatch,
        agent: PropertyAgent,
        template_id: Optional[uuid.UUID] = None,
    ) -> Dict[str, Any]:
        """
        Builds safe, minimal tenant requirement context and renders the outreach message.
        NEVER reveals tenant name, phone, email, AI scores, or private chat history.
        """
        ref_code = f"PM-{str(match.id)[:8].upper()}"

        # Fetch tenant requirement safely
        req = self.db.query(TenantRequirement).filter(TenantRequirement.lead_id == match.lead_id).first()

        listing = match.listing or (
            self.db.query(PropertyListing).filter(PropertyListing.id == match.listing_id).first()
            if match.listing_id
            else None
        )
        prop = match.property or (
            self.db.query(Property).filter(Property.id == match.property_id).first()
            if match.property_id
            else None
        )

        prop_ref = (
            listing.listing_reference
            if (listing and listing.listing_reference)
            else (prop.canonical_name if prop and prop.canonical_name else (prop.building_name if prop and prop.building_name else "your listing"))
        )



        agent_name = agent.full_name or "there"
        move_in_str = "Flexible"
        if req and req.move_in_date:
            move_in_str = str(req.move_in_date)

        lease_str = f"{req.lease_duration_months} months" if (req and req.lease_duration_months) else "12 months"
        occupants_str = str(req.occupants) if (req and req.occupants) else "1-2"
        bedrooms_str = str(req.bedrooms or (listing.bedrooms if listing else 2))


        context_vars = {
            "agent_name": agent_name,
            "property_reference": prop_ref,
            "move_in_date": move_in_str,
            "lease_duration": lease_str,
            "occupants": occupants_str,
            "bedrooms": bedrooms_str,
            "reference_code": ref_code,
        }

        # Check for custom template
        body_template = None
        if template_id:
            tpl = self.db.query(MessageTemplate).filter(MessageTemplate.id == template_id).first()
            if tpl:
                body_template = tpl.body

        if not body_template:
            body_template = (
                "Hi {agent_name}, regarding your listing for {property_reference}. "
                "I have a qualified tenant seeking a {bedrooms}-bed unit, move-in around {move_in_date}, "
                "{lease_duration} lease, {occupants} occupants.\n\n"
                "Could you kindly confirm:\n"
                "1. Is the unit still available?\n"
                "2. Current asking rent?\n"
                "3. Earliest available move-in date?\n"
                "4. Minimum lease term?\n\n"
                "Ref: {reference_code}"
            )

        content = body_template.format(
            agent_name=agent_name,
            property_reference=prop_ref,
            move_in_date=move_in_str,
            lease_duration=lease_str,
            occupants=occupants_str,
            bedrooms=bedrooms_str,
            reference_code=ref_code,
        )

        return {
            "reference_code": ref_code,
            "context_variables": context_vars,
            "content": content,
            "template_id": template_id,
        }

    def preview_outreach(
        self,
        match_id: uuid.UUID,
        template_id: Optional[uuid.UUID] = None,
    ) -> OutreachMessagePreview:
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise ValueError(f"PropertyMatch '{match_id}' not found.")

        mapping = self.mapping_service.resolve_agent_for_match(match)
        if mapping.mapping_status != AgentMappingStatus.READY:
            raise ValueError(f"Agent mapping failed: {mapping.error_message} (status: {mapping.mapping_status})")

        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == mapping.property_agent_id).first()
        ctx = self._build_context_and_content(match, agent, template_id=template_id)

        return OutreachMessagePreview(
            match_id=match.id,
            listing_id=match.listing_id,
            property_agent_id=agent.id,
            recipient_phone=mapping.phone_normalized,
            reference_code=ctx["reference_code"],
            template_id=template_id,
            message_content=ctx["content"],
            context_variables=ctx["context_variables"],
        )

    def send_initial_outreach(
        self,
        match_id: uuid.UUID,
        template_id: Optional[uuid.UUID] = None,
        outreach_type: PropertyAgentOutreachType = PropertyAgentOutreachType.INITIAL_AVAILABILITY_CHECK,
        actor_id: str = "system",
        manual_reason: Optional[str] = None,
    ) -> PropertyAgentOutreach:
        """
        Validates match, maps listing agent, ensures idempotency, dispatches via WhatsAppService,
        creates PropertyAgentOutreach & PropertyAgentConversation, and transitions match to AWAITING_AGENT.
        """
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == match_id).first()
        if not match:
            raise ValueError(f"PropertyMatch '{match_id}' not found.")

        # Idempotency Check first (worker retries / repeated requests)
        idempotency_key = f"property-agent-outreach:{match.id}:{match.listing_id}:{outreach_type.value}"
        legacy_key = f"property-agent-outreach:{match.id}:{outreach_type.value}"
        existing_outreach = (
            self.db.query(PropertyAgentOutreach)
            .filter(PropertyAgentOutreach.idempotency_key.in_([idempotency_key, legacy_key]))
            .first()
        )
        if existing_outreach:
            return existing_outreach

        # 1. Eligibility Checks
        if not match.hard_filter_passed:
            raise ValueError(f"Cannot send outreach: candidate match '{match_id}' failed Phase 3 hard filters.")

        if match.is_stale:
            raise ValueError(f"Cannot send outreach: candidate match '{match_id}' is marked stale. Rescore first.")


        # Check threshold / status
        if match.match_status != PropertyMatchStatus.READY_FOR_AGENT_VERIFICATION.value and not match.manual_override:
            raise ValueError(
                f"Candidate match '{match_id}' is not in READY_FOR_AGENT_VERIFICATION (current: {match.match_status}) "
                "and has no authorized manual override."
            )

        # Check lead qualification status via TenantRequirement
        lead = self.db.query(Lead).filter(Lead.id == match.lead_id).first()
        req = self.db.query(TenantRequirement).filter(TenantRequirement.lead_id == match.lead_id).first()
        if not lead or not req or req.qualification_status != QualificationStatus.QUALIFIED:
            status_val = req.qualification_status.value if req and req.qualification_status else "NO_REQUIREMENT"
            raise ValueError(
                f"Lead '{match.lead_id}' is not in QUALIFIED status (current: {status_val}). Automated agent outreach is blocked."
            )


        # Check listing active & available
        listing = match.listing or self.db.query(PropertyListing).filter(PropertyListing.id == match.listing_id).first()
        from app.models.enums import PropertyListingStatus
        if not listing or listing.listing_status != PropertyListingStatus.ACTIVE:
            raise ValueError("Listing is inactive or missing. Outreach blocked.")

        if listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE.value:
            raise ValueError("Listing is marked UNAVAILABLE. Outreach blocked.")


        # 2. Map agent
        mapping = self.mapping_service.resolve_agent_for_match(match)
        if mapping.mapping_status != AgentMappingStatus.READY:
            raise ValueError(f"Agent mapping failed: {mapping.error_message} (status: {mapping.mapping_status})")

        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == mapping.property_agent_id).first()
        recipient_phone = mapping.phone_normalized

        # 3. Idempotency Check
        idempotency_key = f"property-agent-outreach:{match.id}:{match.listing_id}:{outreach_type.value}"
        existing_outreach = (
            self.db.query(PropertyAgentOutreach)
            .filter(PropertyAgentOutreach.idempotency_key == idempotency_key)
            .first()
        )
        if existing_outreach:
            # If already sent/queued/delivered/read/replied, return safely (idempotent)
            return existing_outreach

        # 4. Build context & content
        ctx = self._build_context_and_content(match, agent, template_id=template_id)
        ref_code = ctx["reference_code"]
        content = ctx["content"]

        # 5. Get or Create PropertyAgentConversation
        conversation = (
            self.db.query(PropertyAgentConversation)
            .filter(
                PropertyAgentConversation.property_agent_id == agent.id,
                PropertyAgentConversation.property_match_id == match.id,
            )
            .first()
        )
        if not conversation:
            conversation = PropertyAgentConversation(
                property_agent_id=agent.id,
                lead_id=match.lead_id,
                property_id=match.property_id,
                listing_id=match.listing_id,
                property_match_id=match.id,
                conversation_type="PROPERTY_AGENT",
                status="ACTIVE",
                reference_code=ref_code,
                last_message_at=func.now(),
            )
            self.db.add(conversation)
            self.db.commit()
            self.db.refresh(conversation)

        # 6. Send message via existing WhatsAppService
        profile = self._get_active_whatsapp_profile()
        wa_msg = self.whatsapp_service.send_message(
            profile_id=profile.id,
            recipient=recipient_phone,
            content=content,
            idempotency_key=f"wa:{idempotency_key}",
            actor_id=actor_id,
        )

        # 7. Create PropertyAgentOutreach record
        outreach = PropertyAgentOutreach(
            lead_id=match.lead_id,
            property_id=match.property_id,
            listing_id=match.listing_id,
            property_match_id=match.id,
            property_agent_id=agent.id,
            conversation_id=conversation.id,
            whatsapp_message_id=wa_msg.id,
            template_id=template_id,
            outreach_type=outreach_type,
            status=PropertyAgentOutreachStatus.SENT,
            provider_message_id=wa_msg.provider_message_id,
            idempotency_key=idempotency_key,
            reference_code=ref_code,
            recipient_phone=recipient_phone,
            message_content=content,
            sent_at=func.now(),
            extra_metadata={
                "manual_reason": manual_reason,
                "context_variables": ctx["context_variables"],
            },
        )
        self.db.add(outreach)

        # 8. Update PropertyMatch status to AWAITING_AGENT
        match.match_status = PropertyMatchStatus.AWAITING_AGENT.value
        match.agent_verification_status = "AWAITING_REPLY"
        conversation.last_message_at = func.now()

        self.db.commit()
        self.db.refresh(outreach)

        # 9. Audit Log
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="PROPERTY_AGENT_OUTREACH_SENT",
                entity_type="PropertyAgentOutreach",
                entity_id=str(outreach.id),
                new_value={
                    "match_id": str(match.id),
                    "property_agent_id": str(agent.id),
                    "recipient_phone": recipient_phone,
                    "reference_code": ref_code,
                    "outreach_type": outreach_type.value,
                    "provider_message_id": wa_msg.provider_message_id,
                },
            )
        )

        # 10. Schedule initial follow-up task and SLA tracking
        try:
            from app.services.property_agent_followup_service import PropertyAgentFollowUpService
            followup_svc = PropertyAgentFollowUpService(self.db, wa_service=self.whatsapp_service)
            followup_svc.schedule_initial_followup(outreach.id)
        except Exception as e:
            logger.warning(f"Failed to schedule initial follow-up for outreach {outreach.id}: {e}")

        return outreach

    def run_bulk_outreach_for_lead(
        self,
        lead_id: uuid.UUID,
        max_candidates: Optional[int] = None,
        template_id: Optional[uuid.UUID] = None,
        actor_id: str = "system",
    ) -> BulkAgentOutreachRunResponse:
        """
        Selects top-N eligible candidate matches for a lead and dispatches outreach.
        """
        candidates = self.selection_service.select_eligible_matches(
            lead_id=lead_id,
            max_candidates=max_candidates,
        )

        sent_count = 0
        queued_count = 0
        failed_count = 0
        already_contacted = 0
        outreach_responses: List[PropertyAgentOutreachResponse] = []

        for match in candidates:
            try:
                outreach = self.send_initial_outreach(
                    match_id=match.id,
                    template_id=template_id,
                    actor_id=actor_id,
                )
                sent_count += 1
                resp = PropertyAgentOutreachResponse.model_validate(outreach)
                if outreach.property_agent:
                    resp.agent_name = outreach.property_agent.full_name
                    resp.agency_name = outreach.property_agent.agency_name
                if outreach.property:
                    resp.property_title = outreach.property.canonical_name or outreach.property.building_name

                outreach_responses.append(resp)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed outreach for match {match.id}: {e}")
                failed_count += 1

        return BulkAgentOutreachRunResponse(
            lead_id=lead_id,
            selected=len(candidates),
            queued=queued_count,
            sent=sent_count,
            failed=failed_count,
            already_contacted=already_contacted,
            outreach_records=outreach_responses,
        )
