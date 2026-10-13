from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
import uuid
from fastapi import HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import (
    MessageDirection,
    MessageAIProcessingStatus,
    QualificationStatus,
    RequirementFieldStatus,
    RequirementSourceType,
    AITaskType,
    ConfidenceAction,
    ClarificationStatus,
)
from app.models.lead import Lead
from app.models.message import WhatsAppMessage
from app.models.tenant_requirement import TenantRequirement
from app.models.tenant_requirement_history import TenantRequirementHistory
from app.ai.enums import TenantIntent
from app.ai.exceptions import AIError
from app.ai.normalizers import (
    normalize_budget,
    normalize_furnishing,
    normalize_lease_duration,
    normalize_locations,
    normalize_move_in_date,
    normalize_occupants,
    normalize_property_type,
)
from app.ai.orchestrator import AIOrchestrator
from app.ai.schemas import (
    NormalizedMessage,
    QualificationAIContext,
    RequirementExtractionResult,
)
from app.repositories.lead_repo import LeadRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.message_ai_processing_repo import MessageAIProcessingRepository
from app.repositories.tenant_requirement_repo import TenantRequirementRepository
from app.repositories.qualification_rule_repo import QualificationRuleRepository
from app.repositories.qualification_clarification_repo import QualificationClarificationRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.services.tenant_requirement_service import TenantRequirementService
from app.services.confidence_policy_service import (
    ConfidencePolicyService,
    HIGH_CONFIDENCE_THRESHOLD,
    MEDIUM_CONFIDENCE_THRESHOLD,
    LOW_CONFIDENCE_THRESHOLD,
)


class TenantUnderstandingResult(BaseModel):
    message_id: Optional[uuid.UUID] = None
    lead_id: Optional[uuid.UUID] = None
    intent: TenantIntent
    intent_confidence: float
    accepted_fields: List[str] = Field(default_factory=list)
    proposed_fields: List[str] = Field(default_factory=list)
    rejected_fields: List[str] = Field(default_factory=list)
    clarification_fields: List[str] = Field(default_factory=list)
    requirements_completion_percentage: int = 0
    missing_required_fields: List[str] = Field(default_factory=list)
    message_summary: Optional[str] = None
    extracted_fields: Dict[str, Any] = Field(default_factory=dict)
    processing_status: str = "PROCESSED"


class TenantMessageUnderstandingService:
    """
    Module 3 Phase 3/7: Tenant Message Understanding Service.
    Coordinates intent classification, structured requirement extraction,
    deterministic domain validation, centralized confidence thresholding,
    clarification tracking, and safe updates through TenantRequirementService.
    
    SAFETY CONSTRAINTS:
    - Never sends WhatsApp replies.
    - Never automatically marks leads as QUALIFIED.
    - Never updates database tables directly from unvalidated AI outputs.
    """

    def __init__(self, db: Session, orchestrator: Optional[AIOrchestrator] = None):
        self.db = db
        self.orchestrator = orchestrator or AIOrchestrator()
        self.lead_repo = LeadRepository(db)
        self.msg_repo = MessageRepository(db)
        self.processing_repo = MessageAIProcessingRepository(db)
        self.req_repo = TenantRequirementRepository(db)
        self.rule_repo = QualificationRuleRepository(db)
        self.audit_repo = AuditRepository(db)
        self.req_service = TenantRequirementService(db)
        self.confidence_policy = ConfidencePolicyService()
        self.clarification_repo = QualificationClarificationRepository(db)

    async def process_tenant_message(
        self,
        message_id: uuid.UUID,
        lead_id: Optional[uuid.UUID] = None,
        actor_id: str = "system",
    ) -> TenantUnderstandingResult:
        """
        Idempotently analyze an incoming tenant message, validate requirements,
        update tenant criteria, and preserve full provenance.
        """

        # 1. Load message
        msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"WhatsAppMessage with ID '{message_id}' not found.",
            )

        if msg.direction != MessageDirection.INBOUND:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only inbound messages from tenants can be analyzed for qualification requirements.",
            )

        # 2. Resolve lead
        lead = None
        if lead_id:
            lead = self.lead_repo.get_by_id(lead_id)
            if not lead:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Lead with ID '{lead_id}' not found.",
                )
        elif msg.sender:
            lead = self.lead_repo.get_by_phone_normalized(msg.sender)

        if not lead:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot associate message '{message_id}' with any registered lead.",
            )

        # 3. Idempotency check: if message already processed, return stored result
        existing_processing = self.processing_repo.get_by_message_id(message_id)
        if existing_processing and existing_processing.status in (
            MessageAIProcessingStatus.PROCESSED,
            MessageAIProcessingStatus.NEEDS_CLARIFICATION,
        ):
            current_req = self.req_repo.get_by_lead_id(lead.id)
            rule = self.rule_repo.get_active_rule()
            missing = self.req_service.get_missing_required_fields(current_req, rule) if current_req else []
            pct = current_req.completion_percentage if current_req else 0

            return TenantUnderstandingResult(
                message_id=msg.id,
                lead_id=lead.id,
                intent=TenantIntent(existing_processing.intent) if existing_processing.intent else TenantIntent.UNCLEAR,
                intent_confidence=float(existing_processing.intent_confidence or 0.0),
                accepted_fields=existing_processing.accepted_fields,
                proposed_fields=existing_processing.proposed_fields,
                rejected_fields=existing_processing.rejected_fields,
                clarification_fields=existing_processing.clarification_fields,
                requirements_completion_percentage=pct,
                missing_required_fields=missing,
                message_summary=existing_processing.message_summary,
                extracted_fields=existing_processing.raw_extraction or {},
                processing_status=existing_processing.status.value,
            )

        # 4. Load current tenant requirements (create baseline if not exists)
        current_req = self.req_repo.get_by_lead_id(lead.id)
        if not current_req:
            current_req = self.req_repo.create(
                lead_id=lead.id,
                data={
                    "currency": "SGD",
                    "qualification_status": QualificationStatus.NOT_STARTED,
                    "completion_percentage": 0,
                },
            )

        rule = self.rule_repo.get_active_rule()

        # 5. Build AI Context
        ctx = QualificationAIContext(
            lead_id=lead.id,
            qualification_status=current_req.qualification_status.value,
            tenant_requirements={
                "preferred_locations": current_req.preferred_locations,
                "budget_min": float(current_req.budget_min) if current_req.budget_min else None,
                "budget_max": float(current_req.budget_max) if current_req.budget_max else None,
                "property_type": current_req.property_type,
                "bedrooms": current_req.bedrooms,
                "move_in_date": current_req.move_in_date.isoformat() if current_req.move_in_date else None,
                "lease_duration_months": current_req.lease_duration_months,
                "occupants": current_req.occupants,
                "furnishing": current_req.furnishing,
            },
            missing_required_fields=self.req_service.get_missing_required_fields(current_req, rule),
            recent_messages=[
                NormalizedMessage(
                    role="tenant",
                    text=msg.content or "",
                    message_id=str(msg.id),
                    timestamp=msg.created_at.isoformat() if msg.created_at else None,
                )
            ],
        )

        # 6. Execute AI Extraction through Orchestrator
        try:
            ai_response = await self.orchestrator.execute_structured(
                task_type=AITaskType.REQUIREMENT_EXTRACTION,
                context=ctx,
                db=self.db,
            )
        except Exception as exc:
            # Record failed processing
            self.processing_repo.create(
                message_id=msg.id,
                lead_id=lead.id,
                status=MessageAIProcessingStatus.FAILED,
                error_message=str(exc),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI requirement extraction failed: {str(exc)}",
            )

        extraction_data: RequirementExtractionResult = ai_response.data


        extracted_fields_raw = extraction_data.fields

        # 7. Domain Validation & Normalization
        validated_fields, rejected_fields, rejected_reasons = self._validate_and_normalize(
            extracted_fields_raw, reference_date=msg.created_at.date() if msg.created_at else date.today()
        )

        # 8. Apply Centralized Confidence Policy & Handle Clarifications
        accepted_fields: List[str] = []
        proposed_fields: List[str] = []
        clarification_fields: List[str] = list(extraction_data.clarification_fields or [])

        # Check for tenant confirmation/rejection of active clarification
        msg_text = (msg.content or "").strip().lower()
        is_affirmation = (
            extraction_data.intent == TenantIntent.CONFIRM_INFORMATION
            or msg_text in ("yes", "yep", "yeah", "correct", "that's right", "sure", "ok", "yes please", "that is right", "right", "exactly", "yes.")
            or msg_text.startswith(("yes, ", "yes ", "correct, ", "that's right"))
        )
        is_negation = (
            extraction_data.intent == TenantIntent.REJECT_INFORMATION
            or msg_text in ("no", "nope", "not really", "wrong", "not that", "no.")
            or msg_text.startswith(("no, ", "no ", "not "))
        )

        active_clar = self.clarification_repo.get_latest_open_for_lead(lead.id)

        if is_affirmation and active_clar and active_clar.proposed_value is not None:
            # Confirm active clarification value!
            clar_field = active_clar.field_name
            confirmed_val = active_clar.proposed_value
            # Deserialize if needed (e.g., date, float, int)
            if clar_field == "move_in_date" and isinstance(confirmed_val, str):
                try:
                    confirmed_val = datetime.strptime(confirmed_val, "%Y-%m-%d").date()
                except ValueError:
                    pass
            elif clar_field in ("budget_max", "budget_min") and isinstance(confirmed_val, (int, float, str)):
                confirmed_val = Decimal(str(confirmed_val))
            elif clar_field in ("occupants", "bedrooms", "lease_duration_months") and isinstance(confirmed_val, (int, str)):
                try:
                    confirmed_val = int(confirmed_val)
                except ValueError:
                    pass

            self.clarification_repo.resolve(active_clar, active_clar.proposed_value)
            self.req_repo.supersede_active_history(current_req.id, clar_field)
            self.req_repo.add_history(
                tenant_requirement_id=current_req.id,
                field_name=clar_field,
                value=str(active_clar.proposed_value),
                status=RequirementFieldStatus.CONFIRMED,
                source_type=RequirementSourceType.TENANT_MESSAGE,
                confidence=Decimal("1.0000"),
                source_message_id=msg.id,
            )
            setattr(current_req, clar_field, confirmed_val)
            if clar_field not in accepted_fields:
                accepted_fields.append(clar_field)

            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action="CLARIFICATION_ANSWERED",
                    entity_type="QualificationClarification",
                    entity_id=str(active_clar.id),
                    new_value={"status": "RESOLVED", "field": clar_field, "value": str(active_clar.proposed_value)},
                )
            )

        elif is_negation and active_clar:
            self.clarification_repo.cancel(active_clar)
            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action="CLARIFICATION_ANSWERED",
                    entity_type="QualificationClarification",
                    entity_id=str(active_clar.id),
                    new_value={"status": "CANCELLED", "field": active_clar.field_name},
                )
            )

        # Evaluate extracted fields through ConfidencePolicyService
        for field_name, item in validated_fields.items():
            conf = item["confidence"]
            val = item["value"]
            needs_conf = item["needs_confirmation"]

            effective_conf = min(conf, 0.70) if needs_conf else conf

            eval_res = self.confidence_policy.evaluate_field(
                field_name=field_name,
                confidence=effective_conf,
                normalized_value=val,
                raw_text=str(val),
            )

            if eval_res.action == ConfidenceAction.ACCEPT:
                # Check for conflict with existing confirmed requirement
                current_val = getattr(current_req, field_name, None)
                if current_val is not None and current_val != val:
                    # If intent indicates explicit update/provide, supersede!
                    if extraction_data.intent in (
                        TenantIntent.UPDATE_REQUIREMENT,
                        TenantIntent.PROVIDE_REQUIREMENTS,
                    ):
                        accepted_fields.append(field_name)
                    else:
                        # Unclear conflict -> propose for confirmation
                        proposed_fields.append(field_name)
                        if field_name not in clarification_fields:
                            clarification_fields.append(field_name)
                        self.clarification_repo.create({
                            "lead_id": lead.id,
                            "field_name": field_name,
                            "reason": "conflicting_with_current_value",
                            "proposed_value": val.isoformat() if isinstance(val, (date, datetime)) else val,
                            "status": ClarificationStatus.WAITING_FOR_TENANT,
                            "attempt_count": 1,
                        })
                else:
                    accepted_fields.append(field_name)
                    # Resolve any active clarification for this field
                    field_clar = self.clarification_repo.get_active_for_field(lead.id, field_name)
                    if field_clar:
                        self.clarification_repo.resolve(field_clar, val.isoformat() if isinstance(val, (date, datetime)) else val)

            elif eval_res.action == ConfidenceAction.ASK_CONFIRMATION:
                proposed_fields.append(field_name)
                if field_name not in clarification_fields:
                    clarification_fields.append(field_name)

                serialized_val = val.isoformat() if isinstance(val, (date, datetime)) else val
                field_clar = self.clarification_repo.get_active_for_field(lead.id, field_name)
                if not field_clar:
                    new_clar = self.clarification_repo.create({
                        "lead_id": lead.id,
                        "field_name": field_name,
                        "reason": eval_res.reason,
                        "proposed_value": serialized_val,
                        "status": ClarificationStatus.WAITING_FOR_TENANT,
                        "attempt_count": 1,
                    })
                    self.audit_repo.log(
                        AuditLogCreate(
                            actor_id=actor_id,
                            action="CLARIFICATION_CREATED",
                            entity_type="QualificationClarification",
                            entity_id=str(new_clar.id),
                            new_value={"lead_id": str(lead.id), "field": field_name, "proposed_value": str(serialized_val)},
                        )
                    )
                else:
                    self.clarification_repo.update(field_clar, {
                        "proposed_value": serialized_val,
                        "status": ClarificationStatus.WAITING_FOR_TENANT,
                        "reason": eval_res.reason,
                    })

            elif eval_res.action == ConfidenceAction.ASK_CLARIFICATION:
                if field_name not in clarification_fields:
                    clarification_fields.append(field_name)
                field_clar = self.clarification_repo.get_active_for_field(lead.id, field_name)
                if not field_clar:
                    self.clarification_repo.create({
                        "lead_id": lead.id,
                        "field_name": field_name,
                        "reason": eval_res.reason,
                        "proposed_value": None,
                        "status": ClarificationStatus.OPEN,
                        "attempt_count": 1,
                    })
                    self.audit_repo.log(
                        AuditLogCreate(
                            actor_id=actor_id,
                            action="CLARIFICATION_CREATED",
                            entity_type="QualificationClarification",
                            new_value={"lead_id": str(lead.id), "field": field_name, "reason": eval_res.reason},
                        )
                    )

            elif eval_res.action == ConfidenceAction.REJECT:
                rejected_fields.append(field_name)
                rejected_reasons[field_name] = eval_res.reason
                if field_name not in clarification_fields:
                    clarification_fields.append(field_name)

        # 9. Update Database records strictly through service logic
        # 9a. Update accepted fields on current_req
        for field_name in accepted_fields:
            if field_name in validated_fields:
                new_val = validated_fields[field_name]["value"]
                conf = validated_fields[field_name]["confidence"]
            else:
                new_val = getattr(current_req, field_name, None)
                conf = 1.0

            if new_val is not None:
                # Supersede previous active history entry
                self.req_repo.supersede_active_history(current_req.id, field_name)

                # Record confirmed history entry
                serialized_val = new_val.isoformat() if isinstance(new_val, date) else new_val
                self.req_repo.add_history(
                    tenant_requirement_id=current_req.id,
                    field_name=field_name,
                    value=serialized_val,
                    status=RequirementFieldStatus.CONFIRMED,
                    source_type=RequirementSourceType.TENANT_MESSAGE,
                    confidence=Decimal(str(round(conf, 4))),
                    source_message_id=msg.id,
                )

                # Apply value to current profile
                setattr(current_req, field_name, new_val)

        # 9b. Record proposed fields in history without updating current active requirement
        for field_name in proposed_fields:
            prop_val = validated_fields[field_name]["value"]
            conf = validated_fields[field_name]["confidence"]
            serialized_val = prop_val.isoformat() if isinstance(prop_val, date) else prop_val

            self.req_repo.add_history(
                tenant_requirement_id=current_req.id,
                field_name=field_name,
                value=serialized_val,
                status=RequirementFieldStatus.PROPOSED,
                source_type=RequirementSourceType.TENANT_MESSAGE,
                confidence=Decimal(str(round(conf, 4))),
                source_message_id=msg.id,
            )

        # 9c. Record rejected fields in history
        for field_name in rejected_fields:
            item = extracted_fields_raw.get(field_name)
            raw_val = item.value if item else None
            conf = item.confidence if item else 0.0

            self.req_repo.add_history(
                tenant_requirement_id=current_req.id,
                field_name=field_name,
                value=raw_val,
                status=RequirementFieldStatus.REJECTED,
                source_type=RequirementSourceType.TENANT_MESSAGE,
                confidence=Decimal(str(round(conf, 4))),
                source_message_id=msg.id,
            )

        # 9d. Recalculate completion percentage & qualification status
        current_req.completion_percentage = self.req_service.calculate_completion_percentage(current_req, rule)
        if current_req.qualification_status == QualificationStatus.NOT_STARTED and accepted_fields:
            current_req.qualification_status = QualificationStatus.IN_PROGRESS

        current_req.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        missing_fields = self.req_service.get_missing_required_fields(current_req, rule)

        # Refresh conversation summary
        from app.services.qualification_memory_service import QualificationMemoryService
        from app.models.enums import SummaryGeneratedBy
        memory_service = QualificationMemoryService(self.db)
        det_text, det_structured = memory_service.build_deterministic_summary(lead.id)
        memory_service.summary_repo.create({
            "lead_id": lead.id,
            "summary_text": det_text,
            "structured_summary": det_structured,
            "generated_by": SummaryGeneratedBy.SYSTEM,
            "last_message_id": msg.id,
        })

        # 10. Persist MessageAIProcessing record
        status_enum = (
            MessageAIProcessingStatus.NEEDS_CLARIFICATION
            if clarification_fields
            else MessageAIProcessingStatus.PROCESSED
        )

        processing_record = self.processing_repo.create(
            message_id=msg.id,
            lead_id=lead.id,
            intent=extraction_data.intent.value,
            intent_confidence=0.95,  # Structured schema overall intent confidence
            status=status_enum,
            accepted_fields=accepted_fields,
            proposed_fields=proposed_fields,
            rejected_fields=rejected_fields,
            clarification_fields=clarification_fields,
            raw_extraction={k: v.model_dump() for k, v in extracted_fields_raw.items()},
            message_summary=extraction_data.message_summary,
        )

        # 11. Audit logging
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="TENANT_MESSAGE_ANALYZED",
                entity_type="WhatsAppMessage",
                entity_id=str(msg.id),
                new_value={
                    "lead_id": str(lead.id),
                    "intent": extraction_data.intent.value,
                    "accepted_fields": accepted_fields,
                    "proposed_fields": proposed_fields,
                    "rejected_fields": rejected_fields,
                    "clarification_fields": clarification_fields,
                    "completion_percentage": current_req.completion_percentage,
                },
            )
        )

        return TenantUnderstandingResult(
            message_id=msg.id,
            lead_id=lead.id,
            intent=extraction_data.intent,
            intent_confidence=0.95,
            accepted_fields=accepted_fields,
            proposed_fields=proposed_fields,
            rejected_fields=rejected_fields,
            clarification_fields=clarification_fields,
            requirements_completion_percentage=current_req.completion_percentage,
            missing_required_fields=missing_fields,
            message_summary=extraction_data.message_summary,
            extracted_fields={k: v.model_dump() for k, v in extracted_fields_raw.items()},
            processing_status=status_enum.value,
        )

    async def extract_from_text(
        self, text: str, reference_date: Optional[date] = None
    ) -> TenantUnderstandingResult:
        """
        Direct text analysis helper for test environments and non-persistent verification.
        Does not touch the database or send messages.
        """
        ctx = QualificationAIContext(
            recent_messages=[NormalizedMessage(role="tenant", text=text)]
        )

        ai_response = await self.orchestrator.execute_structured(
            task_type=AITaskType.REQUIREMENT_EXTRACTION,
            context=ctx,
        )

        extraction_data: RequirementExtractionResult = ai_response.data

        validated_fields, rejected_fields, _ = self._validate_and_normalize(
            extraction_data.fields, reference_date=reference_date or date.today()
        )

        accepted_fields: List[str] = []
        proposed_fields: List[str] = []
        clarification_fields: List[str] = list(extraction_data.clarification_fields or [])

        for field_name, item in validated_fields.items():
            conf = item["confidence"]
            needs_conf = item["needs_confirmation"]

            if conf >= HIGH_CONFIDENCE_THRESHOLD and not needs_conf:
                accepted_fields.append(field_name)
            elif conf >= MEDIUM_CONFIDENCE_THRESHOLD or needs_conf:
                proposed_fields.append(field_name)
                if field_name not in clarification_fields:
                    clarification_fields.append(field_name)
            else:
                rejected_fields.append(field_name)

        return TenantUnderstandingResult(
            intent=extraction_data.intent,
            intent_confidence=0.95,
            accepted_fields=accepted_fields,
            proposed_fields=proposed_fields,
            rejected_fields=rejected_fields,
            clarification_fields=clarification_fields,
            message_summary=extraction_data.message_summary,
            extracted_fields={k: v.model_dump() for k, v in extraction_data.fields.items()},
        )

    def _validate_and_normalize(
        self, fields: Dict[str, Any], reference_date: date
    ) -> Tuple[Dict[str, Any], List[str], Dict[str, str]]:
        """
        Deterministic backend validation and normalization.
        Enforces business rules (budget_min <= budget_max, positive integers, valid enums).
        """
        validated: Dict[str, Any] = {}
        rejected: List[str] = []
        reasons: Dict[str, str] = {}

        for name, item in fields.items():
            raw_val = item.value
            conf = item.confidence
            explicit = item.explicit
            needs_conf = item.needs_confirmation

            if name == "preferred_locations":
                norm_locs = normalize_locations(raw_val)
                if norm_locs:
                    validated[name] = {
                        "value": norm_locs,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf,
                    }
                else:
                    rejected.append(name)
                    reasons[name] = "Locations list empty or invalid."

            elif name == "property_type":
                norm_pt = normalize_property_type(raw_val)
                if norm_pt:
                    validated[name] = {
                        "value": norm_pt,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf,
                    }
                else:
                    rejected.append(name)
                    reasons[name] = "Unsupported property type."

            elif name == "furnishing":
                norm_furn = normalize_furnishing(raw_val)
                if norm_furn:
                    validated[name] = {
                        "value": norm_furn,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf,
                    }
                else:
                    rejected.append(name)
                    reasons[name] = "Unsupported furnishing type."

            elif name in ("budget_min", "budget_max"):
                norm_b = normalize_budget(raw_val)
                raw_str = str(raw_val).lower().strip()
                is_ambiguous_budget = (
                    any(w in raw_str for w in ("around", "maybe", "approx", "about"))
                    or (norm_b is not None and norm_b < 500)
                )
                if norm_b is not None and norm_b >= 0:
                    validated[name] = {
                        "value": norm_b,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf or is_ambiguous_budget,
                    }
                else:
                    rejected.append(name)
                    reasons[name] = f"Invalid budget value: {raw_val}"

            elif name == "bedrooms":
                try:
                    int_bed = int(raw_val)
                    if int_bed >= 0:
                        validated[name] = {
                            "value": int_bed,
                            "confidence": conf,
                            "explicit": explicit,
                            "needs_confirmation": needs_conf,
                        }
                    else:
                        rejected.append(name)
                        reasons[name] = "Bedrooms must be non-negative."
                except (ValueError, TypeError):
                    rejected.append(name)
                    reasons[name] = f"Bedrooms not an integer: {raw_val}"

            elif name == "occupants":
                norm_occ = normalize_occupants(raw_val)
                raw_str = str(raw_val).lower().strip()
                is_ambiguous_occ = any(w in raw_str for w in ("maybe", "around", "or", "approx", "about"))
                if norm_occ and norm_occ > 0:
                    validated[name] = {
                        "value": norm_occ,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf or is_ambiguous_occ,
                    }
                else:
                    rejected.append(name)
                    reasons[name] = "Occupants must be greater than 0."

            elif name == "lease_duration_months":
                norm_ld = normalize_lease_duration(raw_val)
                if norm_ld and norm_ld > 0:
                    validated[name] = {
                        "value": norm_ld,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf,
                    }
                else:
                    rejected.append(name)
                    reasons[name] = "Lease duration must be greater than 0."

            elif name == "move_in_date":
                norm_date_str, is_ambiguous = normalize_move_in_date(raw_val, reference_date)
                if norm_date_str:
                    try:
                        d_obj = datetime.strptime(norm_date_str, "%Y-%m-%d").date()
                        validated[name] = {
                            "value": d_obj,
                            "confidence": conf,
                            "explicit": explicit,
                            "needs_confirmation": needs_conf or is_ambiguous,
                        }
                    except ValueError:
                        rejected.append(name)
                        reasons[name] = f"Invalid date format: {norm_date_str}"
                else:
                    rejected.append(name)
                    reasons[name] = "Could not parse valid move in date."

            elif name == "currency":
                curr_str = str(raw_val).strip().upper()
                if curr_str in ("SGD", "USD", "EUR", "GBP", "AUD"):
                    validated[name] = {
                        "value": curr_str,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf,
                    }
                else:
                    validated[name] = {
                        "value": "SGD",
                        "confidence": 0.90,
                        "explicit": False,
                        "needs_confirmation": False,
                    }

            elif name == "special_requirements":
                if isinstance(raw_val, dict):
                    validated[name] = {
                        "value": raw_val,
                        "confidence": conf,
                        "explicit": explicit,
                        "needs_confirmation": needs_conf,
                    }
                else:
                    rejected.append(name)
                    reasons[name] = "Special requirements must be a dictionary."

        # Cross-field rule: budget_min <= budget_max
        if "budget_min" in validated and "budget_max" in validated:
            if validated["budget_min"]["value"] > validated["budget_max"]["value"]:
                rejected.append("budget_min")
                rejected.append("budget_max")
                reasons["budget_min"] = "budget_min exceeds budget_max."
                reasons["budget_max"] = "budget_max is less than budget_min."
                del validated["budget_min"]
                del validated["budget_max"]

        return validated, rejected, reasons
