import uuid
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.lead import Lead
from app.models.lead_routing import LeadRoutingDecision
from app.models.lead_outreach import LeadOutreach
from app.models.enums import LeadStatus, ConsentStatus, OptOutStatus, ContactEligibility
from app.repositories.lead_repo import LeadRepository
from app.repositories.lead_source_repo import LeadSourceRepository
from app.repositories.agent_repo import AgentRepository
from app.repositories.whatsapp_repo import WhatsAppRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.lead import LeadCreate, LeadUpdate, LeadValidateResponse
from app.schemas.audit import AuditLogCreate
from app.services.phone_service import normalize_phone_number, PhoneNormalizationError


class LeadService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = LeadRepository(db)
        self.source_repo = LeadSourceRepository(db)
        self.agent_repo = AgentRepository(db)
        self.whatsapp_repo = WhatsAppRepository(db)
        self.audit_repo = AuditRepository(db)

    def get_lead_or_404(self, lead_id: uuid.UUID) -> Lead:
        lead = self.repo.get_by_id(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with id '{lead_id}' not found.",
            )
        return lead

    def list_leads(
        self,
        skip: int = 0,
        limit: int = 100,
        status: Optional[LeadStatus] = None,
        source_id: Optional[uuid.UUID] = None,
        assigned_agent_id: Optional[uuid.UUID] = None,
        consent_status: Optional[ConsentStatus] = None,
        opt_out_status: Optional[OptOutStatus] = None,
        contact_eligibility: Optional[ContactEligibility] = None,
        search: Optional[str] = None,
    ) -> List[Lead]:
        return self.repo.list_leads(
            skip=skip,
            limit=limit,
            status=status,
            source_id=source_id,
            assigned_agent_id=assigned_agent_id,
            consent_status=consent_status,
            opt_out_status=opt_out_status,
            contact_eligibility=contact_eligibility,
            search=search,
        )

    def create_lead(self, data: LeadCreate, actor_id: str = "system") -> Lead:
        # Normalize phone
        try:
            phone_normalized = normalize_phone_number(data.phone)
        except PhoneNormalizationError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid phone number: {str(e)}",
            )

        # Validate source if specified
        if data.source_id:
            source = self.source_repo.get_by_id(data.source_id)
            if not source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lead source with id '{data.source_id}' not found.",
                )

        # Validate agent if specified
        if data.assigned_agent_id:
            agent = self.agent_repo.get_by_id(data.assigned_agent_id)
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent with id '{data.assigned_agent_id}' not found.",
                )

        # Validate WhatsApp profile if specified
        if data.assigned_whatsapp_profile_id:
            profile = self.db.query(self.whatsapp_repo.get_by_agent_id(data.assigned_whatsapp_profile_id)) if False else None
            # Fetch by profile primary key
            from app.models.whatsapp import WhatsAppProfile
            profile = self.db.query(WhatsAppProfile).filter(WhatsAppProfile.id == data.assigned_whatsapp_profile_id).first()
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"WhatsApp profile with id '{data.assigned_whatsapp_profile_id}' not found.",
                )

        lead = self.repo.create(data, phone_normalized=phone_normalized)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LEAD_CREATED",
                entity_type="Lead",
                entity_id=str(lead.id),
                new_value={
                    "full_name": lead.full_name,
                    "phone": lead.phone,
                    "phone_normalized": lead.phone_normalized,
                    "status": lead.status.value,
                },
            )
        )
        return lead

    def update_lead(self, lead_id: uuid.UUID, data: LeadUpdate, actor_id: str = "system") -> Lead:
        lead = self.get_lead_or_404(lead_id)

        update_dict = data.model_dump(exclude_unset=True)
        old_values: Dict[str, Any] = {
            "status": lead.status.value if lead.status else None,
            "consent_status": lead.consent_status.value if lead.consent_status else None,
            "opt_out_status": lead.opt_out_status.value if lead.opt_out_status else None,
            "contact_eligibility": lead.contact_eligibility.value if lead.contact_eligibility else None,
        }

        # If phone is updated, re-normalize
        if "phone" in update_dict and update_dict["phone"] is not None:
            try:
                update_dict["phone_normalized"] = normalize_phone_number(update_dict["phone"])
            except PhoneNormalizationError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid phone number: {str(e)}",
                )

        # Check source if updated
        if "source_id" in update_dict and update_dict["source_id"] is not None:
            source = self.source_repo.get_by_id(update_dict["source_id"])
            if not source:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lead source with id '{update_dict['source_id']}' not found.",
                )

        # Check agent if updated
        if "assigned_agent_id" in update_dict and update_dict["assigned_agent_id"] is not None:
            agent = self.agent_repo.get_by_id(update_dict["assigned_agent_id"])
            if not agent:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Agent with id '{update_dict['assigned_agent_id']}' not found.",
                )

        # Check WhatsApp profile if updated
        if "assigned_whatsapp_profile_id" in update_dict and update_dict["assigned_whatsapp_profile_id"] is not None:
            from app.models.whatsapp import WhatsAppProfile
            profile = self.db.query(WhatsAppProfile).filter(WhatsAppProfile.id == update_dict["assigned_whatsapp_profile_id"]).first()
            if not profile:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"WhatsApp profile with id '{update_dict['assigned_whatsapp_profile_id']}' not found.",
                )

        updated = self.repo.update(lead, update_dict)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LEAD_UPDATED",
                entity_type="Lead",
                entity_id=str(updated.id),
                old_value=old_values,
                new_value=update_dict,
            )
        )
        return updated

    def validate_lead(self, lead_id: uuid.UUID, actor_id: str = "system") -> LeadValidateResponse:
        lead = self.get_lead_or_404(lead_id)
        errors: List[str] = []

        try:
            phone_normalized = normalize_phone_number(lead.phone)
            if phone_normalized != lead.phone_normalized:
                self.repo.update(lead, {"phone_normalized": phone_normalized})
        except PhoneNormalizationError as e:
            errors.append(f"Phone validation failed: {str(e)}")

        is_valid = len(errors) == 0

        # Update status
        if is_valid:
            if lead.status == LeadStatus.NEW:
                new_status = LeadStatus.VALIDATING
                self.repo.update(lead, {"status": new_status})
                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="LEAD_VALIDATED",
                        entity_type="Lead",
                        entity_id=str(lead.id),
                        new_value={"status": new_status.value},
                    )
                )
        else:
            self.repo.update(lead, {"status": LeadStatus.FAILED})

        return LeadValidateResponse(
            valid=is_valid,
            phone_normalized=lead.phone_normalized if is_valid else None,
            errors=errors,
        )

    def archive_lead(self, lead_id: uuid.UUID, actor_id: str = "system") -> Lead:
        lead = self.get_lead_or_404(lead_id)
        old_status = lead.status.value

        updated = self.repo.update(lead, {"status": LeadStatus.ARCHIVED})

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LEAD_ARCHIVED",
                entity_type="Lead",
                entity_id=str(updated.id),
                old_value={"status": old_status},
                new_value={"status": LeadStatus.ARCHIVED.value},
            )
        )
        return updated

    def get_routing_history(self, lead_id: uuid.UUID) -> List[LeadRoutingDecision]:
        self.get_lead_or_404(lead_id)
        return self.repo.list_routing_history(lead_id)

    def get_outreach_history(self, lead_id: uuid.UUID) -> List[LeadOutreach]:
        self.get_lead_or_404(lead_id)
        return self.repo.list_outreach(lead_id)

    def check_duplicate(self, lead_id: uuid.UUID, actor_id: str = "system"):
        from app.services.duplicate_service import DuplicateService
        lead = self.get_lead_or_404(lead_id)
        service = DuplicateService(self.db)
        return service.check_duplicate(lead, actor_id=actor_id)

    def override_duplicate(self, lead_id: uuid.UUID, reason: str, actor_id: str = "system") -> Lead:
        from app.services.duplicate_service import DuplicateService
        lead = self.get_lead_or_404(lead_id)
        service = DuplicateService(self.db)
        return service.override_duplicate(lead, reason=reason, actor_id=actor_id)

    def check_contact_eligibility(self, lead_id: uuid.UUID, actor_id: str = "system"):
        from app.services.eligibility_service import EligibilityService
        lead = self.get_lead_or_404(lead_id)
        service = EligibilityService(self.db)
        return service.check_eligibility(lead, actor_id=actor_id)

    def mark_opt_out(self, lead_id: uuid.UUID, reason: Optional[str] = None, actor_id: str = "system") -> Lead:
        from app.services.eligibility_service import EligibilityService
        lead = self.get_lead_or_404(lead_id)
        service = EligibilityService(self.db)
        return service.mark_opt_out(lead, reason=reason, actor_id=actor_id)

    def restore_contact(
        self,
        lead_id: uuid.UUID,
        reason: Optional[str] = None,
        authorized_by: Optional[str] = None,
        authorization_header: Optional[str] = None,
        actor_id: str = "system",
    ) -> Lead:
        from app.services.eligibility_service import EligibilityService
        lead = self.get_lead_or_404(lead_id)
        service = EligibilityService(self.db)
        return service.restore_contact(
            lead,
            reason=reason,
            authorized_by=authorized_by,
            authorization_header=authorization_header,
            actor_id=actor_id,
        )

