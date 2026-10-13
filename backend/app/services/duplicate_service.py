import uuid
from typing import List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.lead import Lead
from app.models.enums import LeadStatus, ContactEligibility
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.lead import (
    LeadDuplicateCheckResponse,
    LeadDuplicateSummary,
)


class DuplicateService:
    def __init__(self, db: Session):
        self.db = db
        self.audit_repo = AuditRepository(db)

    def check_duplicate(self, lead: Lead, actor_id: str = "system") -> LeadDuplicateCheckResponse:
        # Search other non-archived leads, excluding self
        candidates = (
            self.db.query(Lead)
            .filter(Lead.id != lead.id, Lead.status != LeadStatus.ARCHIVED)
            .all()
        )

        match_reasons: List[str] = []
        matched_lead: Optional[Lead] = None

        # Primary check: normalized phone match
        phone_match = next((c for c in candidates if c.phone_normalized == lead.phone_normalized), None)
        if phone_match:
            matched_lead = phone_match
            match_reasons.append("normalized_phone_match")

        # Secondary check: email match
        if lead.email and lead.email.strip():
            lead_email = lead.email.strip().lower()
            email_match = next(
                (c for c in candidates if c.email and c.email.strip().lower() == lead_email),
                None,
            )
            if email_match:
                if matched_lead is None:
                    matched_lead = email_match
                match_reasons.append("email_match")

        if matched_lead:
            # If lead does not have duplicate override and is in intake state, update status
            if not lead.duplicate_override and lead.status in (LeadStatus.NEW, LeadStatus.VALIDATING):
                old_status = lead.status.value
                lead.status = LeadStatus.DUPLICATE
                lead.duplicate_of_id = matched_lead.id
                lead.contact_eligibility = ContactEligibility.INELIGIBLE
                self.db.commit()
                self.db.refresh(lead)

                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="LEAD_DUPLICATE_DETECTED",
                        entity_type="Lead",
                        entity_id=str(lead.id),
                        old_value={"status": old_status},
                        new_value={
                            "status": LeadStatus.DUPLICATE.value,
                            "existing_lead_id": str(matched_lead.id),
                            "match_reasons": match_reasons,
                        },
                    )
                )

            return LeadDuplicateCheckResponse(
                duplicate=True,
                existing_lead_id=matched_lead.id,
                match_reasons=match_reasons,
                existing_lead=LeadDuplicateSummary.model_validate(matched_lead),
            )

        # No duplicate found
        if lead.status == LeadStatus.DUPLICATE and not lead.duplicate_override:
            lead.status = LeadStatus.VALIDATING
            lead.duplicate_of_id = None
            self.db.commit()
            self.db.refresh(lead)

        return LeadDuplicateCheckResponse(
            duplicate=False,
            existing_lead_id=None,
            match_reasons=[],
            existing_lead=None,
        )

    def override_duplicate(self, lead: Lead, reason: str, actor_id: str = "system") -> Lead:
        if not reason or not reason.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Duplicate override reason is required.",
            )

        old_override = lead.duplicate_override
        old_status = lead.status.value

        lead.duplicate_override = True
        lead.duplicate_override_reason = reason.strip()

        # If lead was marked as DUPLICATE, restore to VALIDATING so it can proceed
        if lead.status == LeadStatus.DUPLICATE:
            lead.status = LeadStatus.VALIDATING

        self.db.commit()
        self.db.refresh(lead)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="DUPLICATE_OVERRIDE",
                entity_type="Lead",
                entity_id=str(lead.id),
                old_value={
                    "duplicate_override": old_override,
                    "status": old_status,
                },
                new_value={
                    "duplicate_override": True,
                    "duplicate_override_reason": lead.duplicate_override_reason,
                    "status": lead.status.value,
                },
            )
        )

        return lead
