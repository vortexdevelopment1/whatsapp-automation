import uuid
from decimal import Decimal
from datetime import date
from typing import List, Optional, Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from app.models.tenant_requirement import TenantRequirement
from app.models.tenant_requirement_history import TenantRequirementHistory
from app.models.qualification_rule import QualificationRule
from app.models.enums import (
    QualificationStatus,
    RequirementFieldStatus,
    RequirementSourceType,
)
from app.repositories.tenant_requirement_repo import TenantRequirementRepository
from app.repositories.qualification_rule_repo import QualificationRuleRepository
from app.repositories.lead_repo import LeadRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.tenant_requirement import (
    TenantRequirementCreate,
    TenantRequirementUpdate,
    QualificationProgressResponse,
)


class TenantRequirementService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = TenantRequirementRepository(db)
        self.rule_repo = QualificationRuleRepository(db)
        self.lead_repo = LeadRepository(db)
        self.audit_repo = AuditRepository(db)

    def _get_lead_or_404(self, lead_id: uuid.UUID):
        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with id '{lead_id}' not found.",
            )
        return lead

    def get_requirement_or_404(self, lead_id: uuid.UUID) -> TenantRequirement:
        self._get_lead_or_404(lead_id)
        req = self.repo.get_by_lead_id(lead_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Tenant requirements profile for lead '{lead_id}' not found.",
            )
        return req

    def get_missing_required_fields(
        self, req: TenantRequirement, rule: Optional[QualificationRule] = None
    ) -> List[str]:
        if rule is None:
            rule = self.rule_repo.get_active_rule()

        missing: List[str] = []
        for field in rule.required_fields:
            val = getattr(req, field, None)
            if val is None:
                missing.append(field)
            elif field == "preferred_locations":
                if not isinstance(val, list) or len(val) == 0:
                    missing.append(field)
            elif field in ("property_type", "currency", "furnishing"):
                if isinstance(val, str) and not val.strip():
                    missing.append(field)
            elif field in ("budget_max", "budget_min"):
                if isinstance(val, (int, float, Decimal)) and val <= 0:
                    missing.append(field)
            elif field in ("occupants", "lease_duration_months"):
                if isinstance(val, int) and val <= 0:
                    missing.append(field)
        return missing

    def calculate_completion_percentage(
        self, req: TenantRequirement, rule: Optional[QualificationRule] = None
    ) -> int:
        if rule is None:
            rule = self.rule_repo.get_active_rule()

        required = rule.required_fields
        if not required:
            return 100

        missing = self.get_missing_required_fields(req, rule)
        completed = len(required) - len(missing)
        return int(round((completed / len(required)) * 100))

    def is_ready_for_qualification(
        self, req: TenantRequirement, rule: Optional[QualificationRule] = None
    ) -> bool:
        if rule is None:
            rule = self.rule_repo.get_active_rule()

        missing = self.get_missing_required_fields(req, rule)
        if len(missing) > 0:
            return False

        if req.qualification_status == QualificationStatus.DISQUALIFIED:
            return False

        if req.budget_min is not None and req.budget_max is not None:
            if req.budget_min > req.budget_max:
                return False

        return True

    def create_requirement(
        self, lead_id: uuid.UUID, data: TenantRequirementCreate, actor_id: str = "system"
    ) -> TenantRequirement:
        self._get_lead_or_404(lead_id)
        existing = self.repo.get_by_lead_id(lead_id)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tenant requirements profile already exists for lead '{lead_id}'. Use PATCH to update.",
            )

        data_dict = data.model_dump(exclude={"source_type", "source_message_id"})
        rule = self.rule_repo.get_active_rule()

        # Temporary instance for percentage calculation
        temp_req = TenantRequirement(lead_id=lead_id, **data_dict)
        completion_pct = self.calculate_completion_percentage(temp_req, rule)
        data_dict["completion_percentage"] = completion_pct

        req = self.repo.create(lead_id, data_dict)

        # Record provenance history for all initially provided non-empty fields
        for field_name, value in data_dict.items():
            if value is not None and field_name not in ("completion_percentage", "qualification_status"):
                serialized_val = value.isoformat() if isinstance(value, date) else float(value) if isinstance(value, Decimal) else value
                self.repo.add_history(
                    tenant_requirement_id=req.id,
                    field_name=field_name,
                    value=serialized_val,
                    status=RequirementFieldStatus.CONFIRMED,
                    source_type=data.source_type,
                    source_message_id=data.source_message_id,
                )

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="TENANT_REQUIREMENT_CREATED",
                entity_type="TenantRequirement",
                entity_id=str(req.id),
                new_value={
                    "lead_id": str(lead_id),
                    "completion_percentage": completion_pct,
                    "budget_max": float(req.budget_max) if req.budget_max else None,
                    "property_type": req.property_type,
                },
            )
        )

        return req

    def update_requirement(
        self, lead_id: uuid.UUID, data: TenantRequirementUpdate, actor_id: str = "system"
    ) -> TenantRequirement:
        req = self.get_requirement_or_404(lead_id)
        update_dict = data.model_dump(exclude_unset=True, exclude={"source_type", "source_message_id"})

        if not update_dict:
            return req

        old_values: Dict[str, Any] = {}
        rule = self.rule_repo.get_active_rule()

        for field_name, new_val in update_dict.items():
            old_val = getattr(req, field_name, None)
            if old_val != new_val:
                old_values[field_name] = (
                    old_val.isoformat()
                    if isinstance(old_val, date)
                    else float(old_val)
                    if isinstance(old_val, Decimal)
                    else old_val
                )

                # Supersede previous active history for this field
                self.repo.supersede_active_history(req.id, field_name)

                # Record new confirmed value in history
                serialized_val = (
                    new_val.isoformat()
                    if isinstance(new_val, date)
                    else float(new_val)
                    if isinstance(new_val, Decimal)
                    else new_val
                )
                self.repo.add_history(
                    tenant_requirement_id=req.id,
                    field_name=field_name,
                    value=serialized_val,
                    status=RequirementFieldStatus.CONFIRMED,
                    source_type=data.source_type,
                    source_message_id=data.source_message_id,
                )

        # Apply update
        updated = self.repo.update(req, update_dict)

        # Recalculate completion percentage
        completion_pct = self.calculate_completion_percentage(updated, rule)
        if updated.completion_percentage != completion_pct:
            updated = self.repo.update(updated, {"completion_percentage": completion_pct})

        # Update qualification status progression if in progress
        if updated.qualification_status == QualificationStatus.NOT_STARTED and completion_pct > 0:
            updated = self.repo.update(updated, {"qualification_status": QualificationStatus.IN_PROGRESS})

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="TENANT_REQUIREMENT_UPDATED",
                entity_type="TenantRequirement",
                entity_id=str(updated.id),
                old_value=old_values,
                new_value={
                    k: (
                        v.isoformat()
                        if isinstance(v, date)
                        else float(v)
                        if isinstance(v, Decimal)
                        else v
                    )
                    for k, v in update_dict.items()
                },
            )
        )

        return updated

    def get_qualification_progress(self, lead_id: uuid.UUID) -> QualificationProgressResponse:
        req = self.get_requirement_or_404(lead_id)
        rule = self.rule_repo.get_active_rule()

        missing = self.get_missing_required_fields(req, rule)
        completed = [f for f in rule.required_fields if f not in missing]
        ready = self.is_ready_for_qualification(req, rule)

        return QualificationProgressResponse(
            lead_id=lead_id,
            qualification_status=req.qualification_status,
            completion_percentage=req.completion_percentage,
            ready=ready,
            missing_fields=missing,
            completed_fields=completed,
            required_fields=rule.required_fields,
            optional_fields=rule.optional_fields,
        )

    def list_history(self, lead_id: uuid.UUID) -> List[TenantRequirementHistory]:
        req = self.get_requirement_or_404(lead_id)
        return self.repo.list_history(req.id)
