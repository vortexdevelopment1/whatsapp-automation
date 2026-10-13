import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.lead import Lead
from app.models.enums import LeadStatus, ConsentStatus, OptOutStatus, ContactEligibility
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.lead import LeadEligibilityCheckResponse
from app.services.phone_service import normalize_phone_number, PhoneNormalizationError
from app.services.duplicate_service import DuplicateService


class EligibilityService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)
        self.duplicate_service = DuplicateService(db)

    def check_eligibility(self, lead: Lead, actor_id: str = "system") -> LeadEligibilityCheckResponse:
        reasons: List[str] = []

        # 1. Phone validation
        try:
            if not lead.phone_normalized:
                norm = normalize_phone_number(lead.phone)
                lead.phone_normalized = norm
            else:
                normalize_phone_number(lead.phone_normalized)
        except PhoneNormalizationError:
            reasons.append("invalid_phone")

        # 2. Opt-out check
        if lead.opt_out_status == OptOutStatus.OPTED_OUT or lead.status == LeadStatus.OPTED_OUT:
            reasons.append("opted_out")

        # 3. Consent check: NOT_CONSENTED = INELIGIBLE
        if lead.consent_status == ConsentStatus.NOT_CONSENTED:
            reasons.append("not_consented")

        # 4. Status restrictions: ARCHIVED lead is ineligible for outreach
        if lead.status == LeadStatus.ARCHIVED:
            reasons.append("archived_lead")

        # 5. Duplicate check: unresolved duplicate blocks outreach
        if lead.status == LeadStatus.DUPLICATE and not lead.duplicate_override:
            reasons.append("unresolved_duplicate")
        elif not lead.duplicate_override:
            dup_check = self.duplicate_service.check_duplicate(lead, actor_id=actor_id)
            if dup_check.duplicate:
                reasons.append("unresolved_duplicate")

        # Determine overall eligibility
        hard_blocking_reasons = {"invalid_phone", "opted_out", "not_consented", "archived_lead", "unresolved_duplicate"}
        has_blocking = any(r in hard_blocking_reasons for r in reasons)

        if has_blocking:
            eligibility = ContactEligibility.INELIGIBLE
        elif lead.consent_status == ConsentStatus.UNKNOWN:
            # Rule: UNKNOWN consent must not automatically become ELIGIBLE
            eligibility = ContactEligibility.UNKNOWN
            reasons.append("unknown_consent")
        elif lead.consent_status == ConsentStatus.CONSENTED:
            eligibility = ContactEligibility.ELIGIBLE
        else:
            eligibility = ContactEligibility.UNKNOWN

        old_eligibility = lead.contact_eligibility.value
        lead.contact_eligibility = eligibility

        # Status progression based on eligibility
        if eligibility == ContactEligibility.INELIGIBLE:
            if lead.status in (LeadStatus.NEW, LeadStatus.VALIDATING, LeadStatus.READY_FOR_OUTREACH):
                lead.status = LeadStatus.INELIGIBLE
        elif eligibility == ContactEligibility.ELIGIBLE:
            if lead.status in (LeadStatus.NEW, LeadStatus.VALIDATING):
                lead.status = LeadStatus.READY_FOR_OUTREACH

        self.db.commit()
        self.db.refresh(lead)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="CONTACT_ELIGIBILITY_CHECKED",
                entity_type="Lead",
                entity_id=str(lead.id),
                old_value={"contact_eligibility": old_eligibility},
                new_value={
                    "contact_eligibility": eligibility.value,
                    "reasons": reasons,
                    "status": lead.status.value,
                },
            )
        )

        return LeadEligibilityCheckResponse(
            lead_id=lead.id,
            eligibility=eligibility,
            reasons=reasons,
        )

    def mark_opt_out(self, lead: Lead, reason: Optional[str] = None, actor_id: str = "system") -> Lead:
        old_opt_out = lead.opt_out_status.value
        old_status = lead.status.value
        old_eligibility = lead.contact_eligibility.value

        lead.opt_out_status = OptOutStatus.OPTED_OUT
        lead.status = LeadStatus.OPTED_OUT
        lead.contact_eligibility = ContactEligibility.INELIGIBLE

        self.db.commit()
        self.db.refresh(lead)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="LEAD_OPTED_OUT",
                entity_type="Lead",
                entity_id=str(lead.id),
                old_value={
                    "opt_out_status": old_opt_out,
                    "status": old_status,
                    "contact_eligibility": old_eligibility,
                },
                new_value={
                    "opt_out_status": OptOutStatus.OPTED_OUT.value,
                    "status": LeadStatus.OPTED_OUT.value,
                    "contact_eligibility": ContactEligibility.INELIGIBLE.value,
                    "reason": reason,
                },
            )
        )

        return lead

    def restore_contact(
        self,
        lead: Lead,
        reason: Optional[str] = None,
        authorized_by: Optional[str] = None,
        authorization_header: Optional[str] = None,
        actor_id: str = "system",
    ) -> Lead:
        # Require explicit authorization (via authorized_by in body, or Authorization header)
        if not (authorized_by and authorized_by.strip()) and not (authorization_header and authorization_header.strip()):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Authorization required to restore contact status for an opted-out lead.",
            )

        auth_actor = authorized_by.strip() if authorized_by and authorized_by.strip() else actor_id

        old_opt_out = lead.opt_out_status.value
        old_status = lead.status.value

        lead.opt_out_status = OptOutStatus.ACTIVE
        if lead.status == LeadStatus.OPTED_OUT:
            lead.status = LeadStatus.VALIDATING

        self.db.commit()
        self.db.refresh(lead)

        # Re-check contact eligibility now that opt-out is ACTIVE
        self.check_eligibility(lead, actor_id=auth_actor)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=auth_actor,
                action="LEAD_CONTACT_RESTORED",
                entity_type="Lead",
                entity_id=str(lead.id),
                old_value={
                    "opt_out_status": old_opt_out,
                    "status": old_status,
                },
                new_value={
                    "opt_out_status": OptOutStatus.ACTIVE.value,
                    "status": lead.status.value,
                    "contact_eligibility": lead.contact_eligibility.value,
                    "authorized_by": authorized_by,
                    "reason": reason,
                },
            )
        )

        return lead
