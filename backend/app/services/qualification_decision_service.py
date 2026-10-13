import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.tenant_requirement_history import TenantRequirementHistory
from app.models.qualification_rule import QualificationRule
from app.models.qualification_decision import QualificationDecision
from app.models.enums import (
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    ContactEligibility,
    QualificationStatus,
    RequirementFieldStatus,
    RequirementSourceType,
    QuestionAction,
)
from app.ai.enums import TenantIntent
from app.repositories.lead_repo import LeadRepository
from app.repositories.tenant_requirement_repo import TenantRequirementRepository
from app.repositories.qualification_rule_repo import QualificationRuleRepository
from app.repositories.qualification_decision_repo import QualificationDecisionRepository
from app.repositories.message_ai_processing_repo import MessageAIProcessingRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.qualification_decision import QualificationDecisionResponse
from app.services.qualification_question_service import QualificationQuestionService

logger = logging.getLogger(__name__)

# Valid transitions map: source_status -> set of allowed target statuses
ALLOWED_TRANSITIONS: Dict[QualificationStatus, List[QualificationStatus]] = {
    QualificationStatus.NOT_STARTED: [
        QualificationStatus.IN_PROGRESS,
        QualificationStatus.QUALIFYING,
        QualificationStatus.DISQUALIFIED,
        QualificationStatus.NEEDS_HUMAN_REVIEW,
    ],
    QualificationStatus.IN_PROGRESS: [
        QualificationStatus.WAITING_FOR_TENANT,
        QualificationStatus.QUALIFICATION_COMPLETE,
        QualificationStatus.QUALIFIED,
        QualificationStatus.NEEDS_HUMAN_REVIEW,
        QualificationStatus.DISQUALIFIED,
    ],
    QualificationStatus.QUALIFYING: [
        QualificationStatus.WAITING_FOR_TENANT,
        QualificationStatus.QUALIFICATION_COMPLETE,
        QualificationStatus.QUALIFIED,
        QualificationStatus.NEEDS_HUMAN_REVIEW,
        QualificationStatus.DISQUALIFIED,
        QualificationStatus.IN_PROGRESS,
    ],
    QualificationStatus.WAITING_FOR_TENANT: [
        QualificationStatus.IN_PROGRESS,
        QualificationStatus.QUALIFYING,
        QualificationStatus.QUALIFICATION_COMPLETE,
        QualificationStatus.QUALIFIED,
        QualificationStatus.NEEDS_HUMAN_REVIEW,
        QualificationStatus.DISQUALIFIED,
    ],
    QualificationStatus.QUALIFICATION_COMPLETE: [
        QualificationStatus.QUALIFIED,
        QualificationStatus.NEEDS_HUMAN_REVIEW,
        QualificationStatus.DISQUALIFIED,
        QualificationStatus.IN_PROGRESS,
        QualificationStatus.QUALIFYING,
    ],
    QualificationStatus.NEEDS_HUMAN_REVIEW: [
        QualificationStatus.IN_PROGRESS,
        QualificationStatus.QUALIFYING,
        QualificationStatus.QUALIFIED,
        QualificationStatus.DISQUALIFIED,
    ],
    QualificationStatus.DISQUALIFIED: [
        QualificationStatus.IN_PROGRESS,
        QualificationStatus.QUALIFYING,
        QualificationStatus.QUALIFIED,
        QualificationStatus.NEEDS_HUMAN_REVIEW,
    ],
    QualificationStatus.QUALIFIED: [
        QualificationStatus.NEEDS_HUMAN_REVIEW,
        QualificationStatus.DISQUALIFIED,
    ],
}


def validate_qualification_transition(
    current_status: QualificationStatus,
    target_status: QualificationStatus,
    is_authorized_override: bool = False,
) -> Tuple[bool, Optional[str]]:
    """
    Validates whether transitioning from current_status to target_status is permitted.
    """
    if current_status == target_status:
        return True, None

    # QUALIFIED cannot silently move back to NOT_STARTED
    if current_status == QualificationStatus.QUALIFIED and target_status == QualificationStatus.NOT_STARTED:
        return False, "Cannot transition from QUALIFIED back to NOT_STARTED."

    # If authorized human override, allow transitions except forbidden resets
    if is_authorized_override:
        return True, None

    allowed = ALLOWED_TRANSITIONS.get(current_status, [])
    if target_status in allowed:
        return True, None

    return False, f"Transition from {current_status.value} to {target_status.value} is not permitted."


class QualificationDecisionService:
    """
    Deterministic domain service evaluating whether a tenant qualifies for rental matching.
    The LLM NEVER directly marks a tenant QUALIFIED or DISQUALIFIED;
    this service evaluates validated criteria, business rules, and contact eligibility.
    """

    def __init__(self, db: Session):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.req_repo = TenantRequirementRepository(db)
        self.rule_repo = QualificationRuleRepository(db)
        self.decision_repo = QualificationDecisionRepository(db)
        self.processing_repo = MessageAIProcessingRepository(db)
        self.audit_repo = AuditRepository(db)
        self.q_service = QualificationQuestionService(db)

    def _get_lead_or_404(self, lead_id: uuid.UUID) -> Lead:
        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Lead with ID '{lead_id}' not found.",
            )
        return lead

    def _get_requirement_or_404(self, lead_id: uuid.UUID) -> TenantRequirement:
        req = self.req_repo.get_by_lead_id(lead_id)
        if not req:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"TenantRequirement profile for lead '{lead_id}' not found.",
            )
        return req

    @classmethod
    def validate_qualification_transition(
        cls,
        current_status: QualificationStatus,
        target_status: QualificationStatus,
        is_authorized_override: bool = False,
    ) -> bool:
        is_valid, err = validate_qualification_transition(current_status, target_status, is_authorized_override)
        if not is_valid:
            raise ValueError(f"Invalid qualification transition: {err}")
        return True

    def get_decision_history(self, lead_id: uuid.UUID):
        return self.decision_repo.list_for_lead(lead_id)

    def evaluate_qualification(
        self,
        lead_id: uuid.UUID,
        apply: bool = False,
        actor_id: str = "system",
        override_decision: Optional[QualificationStatus] = None,
        override_reason: Optional[str] = None,
        is_operator_authorized: bool = True,
        human_override_status: Optional[Any] = None,
        evaluated_by: Optional[str] = None,
    ) -> QualificationDecisionResponse:
        """
        Calculates deterministic qualification decision for a lead.
        Supports preview (apply=False) and state application (apply=True).
        """
        lead = self._get_lead_or_404(lead_id)
        req = self.req_repo.get_by_lead_id(lead_id)
        rule = self.rule_repo.get_active_rule()

        rule_version = rule.version or "v1"

        if human_override_status is not None and override_decision is None:
            if isinstance(human_override_status, str):
                override_decision = QualificationStatus(human_override_status)
            else:
                override_decision = human_override_status

        if evaluated_by is not None and actor_id == "system":
            actor_id = evaluated_by

        # Case 0: Human override requested
        if override_decision is not None:
            if not is_operator_authorized:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Unauthorized to perform manual qualification override.",
                )
            if not override_reason or not override_reason.strip():
                raise ValueError("Override reason is required for manual qualification override.")

            current_status = req.qualification_status if req else QualificationStatus.NOT_STARTED
            is_valid_t, err_msg = validate_qualification_transition(
                current_status, override_decision, is_authorized_override=True
            )
            if not is_valid_t:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

            decision = override_decision
            reason_codes = ["MANUAL_HUMAN_OVERRIDE", "HUMAN_OVERRIDE"]
            missing_fields = []
            blocking_fields = []
            completion_pct = req.completion_percentage if req else 0

            if apply and req:
                req.qualification_status = decision
                self.db.commit()

                # Store decision history
                saved_dec = self.decision_repo.create({
                    "lead_id": lead.id,
                    "tenant_requirement_id": req.id if req else None,
                    "decision": decision,
                    "reason_codes": reason_codes,
                    "rule_version": rule_version,
                    "completion_percentage": completion_pct,
                    "missing_fields": missing_fields,
                    "blocking_fields": blocking_fields,
                    "evaluated_by": actor_id,
                    "evaluation_source": "HUMAN",
                    "override_reason": override_reason.strip(),
                    "applied": True,
                })

                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="QUALIFICATION_MANUAL_OVERRIDE",
                        entity_type="TenantRequirement",
                        entity_id=str(req.id),
                        new_value={
                            "decision": decision.value,
                            "reason": override_reason.strip(),
                            "rule_version": rule_version,
                        },
                    )
                )

                return QualificationDecisionResponse(
                    id=saved_dec.id,
                    lead_id=lead.id,
                    tenant_requirement_id=req.id if req else None,
                    decision=decision,
                    reason_codes=reason_codes,
                    missing_fields=missing_fields,
                    blocking_fields=blocking_fields,
                    completion_percentage=completion_pct,
                    rule_version=rule_version,
                    applied=True,
                    evaluated_by=actor_id,
                    evaluation_source="HUMAN",
                    override_reason=override_reason.strip(),
                    created_at=saved_dec.created_at,
                )
            else:
                return QualificationDecisionResponse(
                    lead_id=lead.id,
                    tenant_requirement_id=req.id if req else None,
                    decision=decision,
                    reason_codes=reason_codes,
                    missing_fields=missing_fields,
                    blocking_fields=blocking_fields,
                    completion_percentage=completion_pct,
                    rule_version=rule_version,
                    applied=False,
                    evaluated_by=actor_id,
                    evaluation_source="HUMAN",
                    override_reason=override_reason.strip(),
                )

        # Requirement profile check
        if not req:
            return QualificationDecisionResponse(
                lead_id=lead.id,
                tenant_requirement_id=None,
                decision=QualificationStatus.NOT_STARTED,
                reason_codes=["NO_REQUIREMENT_PROFILE"],
                missing_fields=list(rule.required_fields or []),
                blocking_fields=list(rule.required_fields or []),
                completion_percentage=0,
                rule_version=rule_version,
                applied=False,
            )

        reason_codes: List[str] = []
        blocking_fields: List[str] = []

        # 1. Contact eligibility & Lead state check (Module 2 reuse)
        if lead.status == LeadStatus.ARCHIVED:
            if apply:
                raise ValueError("Cannot update qualification for an ARCHIVED lead.")
            reason_codes.append("LEAD_ARCHIVED")
            return QualificationDecisionResponse(
                lead_id=lead.id,
                tenant_requirement_id=req.id,
                decision=QualificationStatus.DISQUALIFIED,
                reason_codes=reason_codes,
                missing_fields=[],
                blocking_fields=["lead_status"],
                completion_percentage=req.completion_percentage,
                rule_version=rule_version,
                applied=False,
            )

        if lead.opt_out_status == OptOutStatus.OPTED_OUT:
            reason_codes.append("LEAD_OPTED_OUT")
            reason_codes.append("CONTACT_NOT_ELIGIBLE")
            blocking_fields.append("opt_out_status")
        elif lead.consent_status == ConsentStatus.NOT_CONSENTED:
            reason_codes.append("LEAD_NOT_CONSENTED")
            reason_codes.append("CONTACT_NOT_ELIGIBLE")
            blocking_fields.append("consent_status")
        elif lead.contact_eligibility != ContactEligibility.ELIGIBLE:
            reason_codes.append("CONTACT_NOT_ELIGIBLE")
            blocking_fields.append("contact_eligibility")

        # 2. Inspect missing fields, completed fields, clarifications
        completed, missing, clarification, completion_pct = self.q_service.calculate_field_states(req, rule)

        if missing:
            reason_codes.append("MISSING_REQUIRED_FIELDS")
            blocking_fields.extend(missing)

        if clarification:
            reason_codes.append("PENDING_CLARIFICATION")
            blocking_fields.extend(clarification)

        # 3. Deterministic Validation Checks on present fields
        validation_errors: List[str] = []

        # Budget max validation
        if req.budget_max is not None:
            if req.budget_max <= 0:
                validation_errors.append("budget_max")
                reason_codes.append("INVALID_BUDGET_VALUE")
        # Budget min <= budget_max check
        if req.budget_min is not None and req.budget_max is not None:
            if req.budget_min > req.budget_max:
                validation_errors.append("budget_min")
                reason_codes.append("UNRESOLVED_REQUIREMENT_CONFLICT")
                blocking_fields.append("budget_min")

        # Occupants validation
        if req.occupants is not None:
            if req.occupants <= 0:
                validation_errors.append("occupants")
                reason_codes.append("INVALID_OCCUPANTS_VALUE")

        # Lease duration validation
        if req.lease_duration_months is not None:
            if req.lease_duration_months <= 0:
                validation_errors.append("lease_duration_months")
                reason_codes.append("INVALID_LEASE_DURATION")

        # Locations validation
        if req.preferred_locations is not None:
            if not isinstance(req.preferred_locations, list) or len(req.preferred_locations) == 0:
                validation_errors.append("preferred_locations")
                reason_codes.append("INVALID_LOCATIONS")

        if validation_errors:
            blocking_fields.extend(validation_errors)

        # 4. Check for unresolved conflicts in history
        history = self.req_repo.list_history(req.id)
        # Check if any required field is marked REJECTED without subsequent CONFIRMED
        field_status_counts: Dict[str, List[RequirementFieldStatus]] = {}
        for h in history:
            field_status_counts.setdefault(h.field_name, []).append(h.status)

        for f_name, statuses in field_status_counts.items():
            if f_name in (rule.required_fields or []):
                # Latest status is statuses[0] because list_history is ordered by created_at DESC
                if statuses and statuses[0] == RequirementFieldStatus.REJECTED:
                    reason_codes.append("UNRESOLVED_REQUIREMENT_CONFLICT")
                    blocking_fields.append(f_name)

        # 5. Check human review conditions
        latest_proc = self.processing_repo.get_latest_for_lead(lead.id)
        if latest_proc and latest_proc.intent == TenantIntent.ASK_FOR_HUMAN.value:
            reason_codes.append("TENANT_REQUESTED_HUMAN")
            blocking_fields.append("intent")

        # 6. Evaluate Configured Disqualification Rules from QualificationRule
        disq_rules: List[Dict[str, Any]] = list(rule.disqualification_rules or [])
        tripped_disq_rules: List[str] = []

        for d_rule in disq_rules:
            if not isinstance(d_rule, dict):
                continue
            r_type = d_rule.get("rule_type", "")
            r_field = d_rule.get("field", "")
            reason = d_rule.get("reason_code", "CONFIGURED_DISQUALIFICATION_TRIGGERED")

            # Min lease duration check
            if r_type == "MIN_LEASE_DURATION" or r_field == "lease_duration_months" or d_rule.get("operator") in ("lt", "<"):
                min_val = d_rule.get("min_value", d_rule.get("threshold", d_rule.get("value")))
                if min_val is not None and req.lease_duration_months is not None:
                    if req.lease_duration_months < int(min_val):
                        tripped_disq_rules.append(reason)
                        blocking_fields.append("lease_duration_months")

            # Min budget check
            elif r_type == "MIN_BUDGET" or (r_field == "budget_max" and "min_value" in d_rule):
                min_b = d_rule.get("min_value", d_rule.get("threshold"))
                if min_b is not None and req.budget_max is not None:
                    if float(req.budget_max) < float(min_b):
                        tripped_disq_rules.append(reason)
                        blocking_fields.append("budget_max")

            # Unsupported property type check
            elif r_type == "UNSUPPORTED_PROPERTY_TYPE" or r_field == "property_type":
                unsupported = [v.upper() for v in d_rule.get("unsupported_values", [])]
                if req.property_type and req.property_type.upper() in unsupported:
                    tripped_disq_rules.append(reason)
                    blocking_fields.append("property_type")

        # Remove duplicate blocking fields while preserving order
        unique_blocking = list(dict.fromkeys(blocking_fields))
        unique_reasons = list(dict.fromkeys(reason_codes))

        # 7. Decision Synthesis
        final_decision: QualificationStatus

        # (a) Disqualification check
        if tripped_disq_rules:
            final_decision = QualificationStatus.DISQUALIFIED
            unique_reasons.extend(tripped_disq_rules)
            unique_reasons = list(dict.fromkeys(unique_reasons))
        elif "CONTACT_NOT_ELIGIBLE" in unique_reasons or "LEAD_OPTED_OUT" in unique_reasons:
            final_decision = QualificationStatus.DISQUALIFIED

        # (b) Human Review check
        elif (
            "TENANT_REQUESTED_HUMAN" in unique_reasons
            or "UNRESOLVED_REQUIREMENT_CONFLICT" in unique_reasons
            or any("CONFLICT" in r for r in unique_reasons)
            or req.qualification_status == QualificationStatus.NEEDS_HUMAN_REVIEW
        ):
            final_decision = QualificationStatus.NEEDS_HUMAN_REVIEW

        # (c) In-Progress / Missing fields check
        elif missing or clarification or validation_errors:
            if completion_pct > 0 or req.qualification_status in (QualificationStatus.IN_PROGRESS, QualificationStatus.WAITING_FOR_TENANT, QualificationStatus.QUALIFYING):
                final_decision = QualificationStatus.IN_PROGRESS
            else:
                final_decision = QualificationStatus.NOT_STARTED

        # (d) Fully complete & valid -> QUALIFIED!
        elif completion_pct == 100 and not unique_blocking:
            final_decision = QualificationStatus.QUALIFIED
            unique_reasons = [
                "ALL_REQUIRED_FIELDS_COMPLETE",
                "ALL_REQUIRED_FIELDS_VALID",
                "NO_BLOCKING_CLARIFICATIONS",
            ]
        else:
            final_decision = QualificationStatus.IN_PROGRESS

        # 8. Commit and state application if apply=True
        if apply:
            current_status = req.qualification_status
            is_valid_t, err_msg = validate_qualification_transition(current_status, final_decision)
            if not is_valid_t:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

            # Idempotency check: see if latest decision is identical
            latest_decision = self.decision_repo.get_latest_for_lead(lead.id)
            is_duplicate = (
                latest_decision is not None
                and latest_decision.decision == final_decision
                and latest_decision.rule_version == rule_version
                and latest_decision.reason_codes == unique_reasons
                and req.qualification_status == final_decision
            )

            if not is_duplicate:
                status_changed = (req.qualification_status != final_decision)
                req.qualification_status = final_decision
                req.completion_percentage = completion_pct

                self.db.commit()

                # Store decision history
                saved_dec = self.decision_repo.create({
                    "lead_id": lead.id,
                    "tenant_requirement_id": req.id,
                    "decision": final_decision,
                    "reason_codes": unique_reasons,
                    "rule_version": rule_version,
                    "completion_percentage": completion_pct,
                    "missing_fields": missing,
                    "blocking_fields": unique_blocking,
                    "evaluated_by": actor_id,
                    "evaluation_source": "SYSTEM",
                    "applied": True,
                })

                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="QUALIFICATION_EVALUATED",
                        entity_type="TenantRequirement",
                        entity_id=str(req.id),
                        new_value={
                            "decision": final_decision.value,
                            "rule_version": rule_version,
                            "reasons": unique_reasons,
                        },
                    )
                )

                if status_changed:
                    self.audit_repo.log(
                        AuditLogCreate(
                            actor_id=actor_id,
                            action="QUALIFICATION_STATE_CHANGED",
                            entity_type="TenantRequirement",
                            entity_id=str(req.id),
                            new_value={
                                "from_status": current_status.value,
                                "to_status": final_decision.value,
                            },
                        )
                    )

                return QualificationDecisionResponse(
                    id=saved_dec.id,
                    lead_id=lead.id,
                    tenant_requirement_id=req.id,
                    decision=final_decision,
                    reason_codes=unique_reasons,
                    missing_fields=missing,
                    blocking_fields=unique_blocking,
                    completion_percentage=completion_pct,
                    rule_version=rule_version,
                    applied=True,
                    evaluated_by=actor_id,
                    evaluation_source="SYSTEM",
                    created_at=saved_dec.created_at,
                )
            else:
                return QualificationDecisionResponse(
                    id=latest_decision.id,
                    lead_id=lead.id,
                    tenant_requirement_id=req.id,
                    decision=final_decision,
                    reason_codes=unique_reasons,
                    missing_fields=missing,
                    blocking_fields=unique_blocking,
                    completion_percentage=completion_pct,
                    rule_version=rule_version,
                    applied=True,
                    evaluated_by=latest_decision.evaluated_by,
                    evaluation_source=latest_decision.evaluation_source,
                    created_at=latest_decision.created_at,
                )

        # Preview mode (apply=False)
        return QualificationDecisionResponse(
            lead_id=lead.id,
            tenant_requirement_id=req.id,
            decision=final_decision,
            reason_codes=unique_reasons,
            missing_fields=missing,
            blocking_fields=unique_blocking,
            completion_percentage=completion_pct,
            rule_version=rule_version,
            applied=False,
            evaluated_by=actor_id,
            evaluation_source="SYSTEM",
        )
