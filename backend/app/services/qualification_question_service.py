import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import date
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.qualification_rule import QualificationRule
from app.models.qualification_question import QualificationQuestion
from app.models.enums import (
    QuestionAction,
    QuestionType,
    QualificationQuestionStatus,
    RequirementFieldStatus,
    AITaskType,
    ClarificationStatus,
)
from app.ai.enums import TenantIntent, MessageRole
from app.ai.schemas import (
    QuestionInstruction,
    QuestionResponseResult,
    NextQuestionResponse,
    QualificationPreviewResponse,
    QualificationAIContext,
    NormalizedMessage,
)
from app.ai.orchestrator import AIOrchestrator
from app.repositories.qualification_question_repo import QualificationQuestionRepository
from app.repositories.qualification_rule_repo import QualificationRuleRepository
from app.repositories.lead_repo import LeadRepository
from app.repositories.tenant_requirement_repo import TenantRequirementRepository
from app.repositories.message_ai_processing_repo import MessageAIProcessingRepository
from app.repositories.qualification_clarification_repo import QualificationClarificationRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.services.tenant_requirement_service import TenantRequirementService

logger = logging.getLogger(__name__)

# Configurable limits
MAX_CLARIFICATION_ATTEMPTS_PER_FIELD = 2

# Deterministic fallback templates
FALLBACK_QUESTIONS: Dict[str, str] = {
    "preferred_locations": "Which area or location are you looking for?",
    "budget_max": "What is your approximate monthly rental budget?",
    "budget_min": "What is your minimum monthly budget?",
    "property_type": "What type of property are you looking for?",
    "move_in_date": "When are you planning to move in?",
    "lease_duration_months": "How long are you planning to rent the property for?",
    "occupants": "How many people will be staying in the property?",
    "bedrooms": "How many bedrooms do you need?",
    "furnishing": "Do you prefer furnished, partially furnished, or unfurnished?",
    "special_requirements": "Do you have any specific requirements, such as pets or parking?",
}


class QualificationQuestionService:
    """
    Deterministic qualification question engine.
    Decides WHAT to ask (or whether to escalate to human review).
    Uses AI strictly to phrase HOW to ask it naturally.
    """

    def __init__(
        self,
        db: Session,
        orchestrator: Optional[AIOrchestrator] = None,
        max_clarification_attempts: int = MAX_CLARIFICATION_ATTEMPTS_PER_FIELD,
    ):
        self.db = db
        self.orchestrator = orchestrator or AIOrchestrator()
        self.max_clarification_attempts = max_clarification_attempts

        self.lead_repo = LeadRepository(db)
        self.rule_repo = QualificationRuleRepository(db)
        self.req_repo = TenantRequirementRepository(db)
        self.question_repo = QualificationQuestionRepository(db)
        self.processing_repo = MessageAIProcessingRepository(db)
        self.clar_repo = QualificationClarificationRepository(db)
        self.audit_repo = AuditRepository(db)
        self.req_service = TenantRequirementService(db)

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

    def calculate_field_states(
        self, req: TenantRequirement, rule: Optional[QualificationRule] = None
    ) -> Tuple[List[str], List[str], List[str], int]:
        """
        Calculates:
        (completed_fields, missing_fields, clarification_fields, completion_percentage)
        """
        if rule is None:
            rule = self.rule_repo.get_active_rule()

        required_fields: List[str] = list(rule.required_fields or [])

        # 1. Inspect latest history for PROPOSED or REJECTED status
        history = self.req_repo.list_history(req.id)
        field_latest_status: Dict[str, RequirementFieldStatus] = {}
        for entry in history:
            if entry.field_name not in field_latest_status and entry.status != RequirementFieldStatus.SUPERSEDED:
                field_latest_status[entry.field_name] = entry.status

        # 2. Inspect latest AI processing for clarification fields
        latest_proc = self.processing_repo.get_latest_for_lead(req.lead_id)
        ai_clarifications = set(latest_proc.clarification_fields or []) if latest_proc else set()

        # Check active records in qualification_clarifications table
        active_clar_fields = set()
        if hasattr(self, "clar_repo"):
            active_clar_records = self.clar_repo.list_for_lead(req.lead_id)
            for c in active_clar_records:
                if c.status in (ClarificationStatus.OPEN, ClarificationStatus.WAITING_FOR_TENANT):
                    active_clar_fields.add(c.field_name)

        completed: List[str] = []
        missing: List[str] = []
        clarification: List[str] = []

        for field in required_fields:
            val = getattr(req, field, None)
            is_clarification = (
                field in ai_clarifications
                or field in active_clar_fields
                or field_latest_status.get(field) == RequirementFieldStatus.PROPOSED
            )

            if is_clarification:
                clarification.append(field)
                continue

            # Deterministic value validation
            is_valid = True
            if val is None:
                is_valid = False
            elif field == "preferred_locations":
                if not isinstance(val, list) or len(val) == 0:
                    is_valid = False
            elif field in ("property_type", "furnishing", "currency"):
                if not isinstance(val, str) or not val.strip() or val.upper() == "UNKNOWN":
                    is_valid = False
            elif field in ("budget_max", "budget_min"):
                if not isinstance(val, (int, float, Decimal)) or val <= 0:
                    is_valid = False
            elif field in ("occupants", "lease_duration_months"):
                if not isinstance(val, int) or val <= 0:
                    is_valid = False
            elif field == "bedrooms":
                if not isinstance(val, int) or val < 0:
                    is_valid = False

            if is_valid and field_latest_status.get(field, RequirementFieldStatus.CONFIRMED) != RequirementFieldStatus.REJECTED:
                completed.append(field)
            else:
                missing.append(field)

        completion_pct = (
            int(round((len(completed) / len(required_fields)) * 100))
            if required_fields
            else 100
        )
        return completed, missing, clarification, completion_pct

    def get_next_question_instruction(
        self, lead_id: uuid.UUID, collect_optional: bool = False
    ) -> QuestionInstruction:
        """
        Authoritative deterministic decision on WHAT to ask next.
        Follows priority:
        1. Human review conditions (tenant requested human, budget contradiction, max clarification exceeded)
        2. Clarification priority (first unresolved clarification field by configured question_order)
        3. Missing required fields (first missing required field by configured question_order)
        4. Optional fields (if explicitly configured)
        5. No question needed (all required fields complete)
        """
        self._get_lead_or_404(lead_id)
        req = self._get_requirement_or_404(lead_id)
        rule = self.rule_repo.get_active_rule()

        # 1. Check human escalation conditions
        # (a) Tenant explicitly asked for human
        latest_proc = self.processing_repo.get_latest_for_lead(lead_id)
        if latest_proc and latest_proc.intent == TenantIntent.ASK_FOR_HUMAN.value:
            return QuestionInstruction(
                action=QuestionAction.HUMAN_REVIEW,
                reason="tenant_requested_human",
                context={"intent": "ASK_FOR_HUMAN"},
            )

        # (b) Inconsistent data conflict (e.g. budget_min > budget_max)
        if req.budget_min is not None and req.budget_max is not None:
            if req.budget_min > req.budget_max:
                return QuestionInstruction(
                    action=QuestionAction.HUMAN_REVIEW,
                    reason="unresolved_budget_conflict",
                    context={
                        "budget_min": float(req.budget_min),
                        "budget_max": float(req.budget_max),
                    },
                )

        completed, missing, clarification, completion_pct = self.calculate_field_states(req, rule)

        # Question ordering from active qualification rule
        question_order: List[str] = list(rule.question_order or [])
        if not question_order:
            question_order = [
                "preferred_locations",
                "budget_max",
                "property_type",
                "move_in_date",
                "lease_duration_months",
                "occupants",
                "bedrooms",
                "furnishing",
                "special_requirements",
            ]

        # 2. Priority 1: Clarification fields
        if clarification:
            # Sort clarification fields by configured question_order
            sorted_clarifications = sorted(
                clarification,
                key=lambda f: question_order.index(f) if f in question_order else 999,
            )
            target_field = sorted_clarifications[0]

            # Check attempt limit
            attempts = self.question_repo.count_attempts_for_field(
                lead_id=lead_id,
                field_name=target_field,
                question_types=[QuestionType.CLARIFICATION, QuestionType.CONFIRMATION],
            )

            if attempts >= self.max_clarification_attempts:
                clar = self.clar_repo.get_active_for_field(lead_id, target_field)
                if clar:
                    self.clar_repo.escalate(clar)
                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id="system",
                        action="CLARIFICATION_LIMIT_EXCEEDED",
                        entity_type="TenantRequirement",
                        entity_id=str(req.id),
                        new_value={"field": target_field, "attempts": attempts},
                    )
                )
                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id="system",
                        action="CLARIFICATION_ESCALATED",
                        entity_type="QualificationClarification",
                        entity_id=str(clar.id) if clar else str(req.id),
                        new_value={"field": target_field, "attempts": attempts},
                    )
                )
                return QuestionInstruction(
                    action=QuestionAction.HUMAN_REVIEW,
                    field=target_field,
                    reason="max_clarification_attempts_exceeded",
                    context={"field": target_field, "attempts": attempts},
                )

            # Retrieve proposed value if any
            proposed_val = None
            history = self.req_repo.list_history(req.id)
            for h in history:
                if h.field_name == target_field and h.status == RequirementFieldStatus.PROPOSED:
                    proposed_val = h.value
                    break

            clar = self.clar_repo.get_active_for_field(lead_id, target_field)
            if clar:
                self.clar_repo.increment_attempt(clar)
                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id="system",
                        action="CLARIFICATION_ASKED",
                        entity_type="QualificationClarification",
                        entity_id=str(clar.id),
                        new_value={"field": target_field, "attempt": attempts + 1},
                    )
                )

            return QuestionInstruction(
                action=QuestionAction.ASK_CLARIFICATION,
                field=target_field,
                question_type=QuestionType.CLARIFICATION,
                reason="field_requires_clarification",
                context={
                    "proposed_value": proposed_val,
                    "attempts": attempts + 1,
                    "field": target_field,
                },
            )

        # 3. Priority 2: Missing required fields
        if missing:
            # Sort missing fields by configured question_order
            sorted_missing = sorted(
                missing,
                key=lambda f: question_order.index(f) if f in question_order else 999,
            )
            target_field = sorted_missing[0]

            return QuestionInstruction(
                action=QuestionAction.ASK_FIELD,
                field=target_field,
                question_type=QuestionType.MISSING_FIELD,
                reason="required_field_missing",
                context={"current_value": None, "field": target_field},
            )

        # 4. Priority 3: Optional fields if configured
        if collect_optional and rule.optional_fields:
            optional_missing: List[str] = []
            for opt_field in rule.optional_fields:
                val = getattr(req, opt_field, None)
                if val is None or (isinstance(val, list) and len(val) == 0):
                    optional_missing.append(opt_field)

            if optional_missing:
                sorted_opt = sorted(
                    optional_missing,
                    key=lambda f: question_order.index(f) if f in question_order else 999,
                )
                target_field = sorted_opt[0]
                return QuestionInstruction(
                    action=QuestionAction.ASK_FIELD,
                    field=target_field,
                    question_type=QuestionType.MISSING_FIELD,
                    reason="optional_field_missing",
                    context={"current_value": None, "field": target_field},
                )

        # 5. Priority 4: All required fields complete
        return QuestionInstruction(
            action=QuestionAction.NO_QUESTION,
            reason="all_required_fields_complete",
            context={"completion_percentage": 100},
        )

    def get_fallback_question(
        self, field: Optional[str], question_type: Optional[QuestionType], context: Dict[str, Any]
    ) -> str:
        """Deterministic fallback question generator."""
        if not field:
            return "Could you provide more details about your rental preferences?"

        if question_type in (QuestionType.CLARIFICATION, QuestionType.CONFIRMATION):
            proposed = context.get("proposed_value")
            if proposed is not None:
                if field == "budget_max":
                    return f"Just to confirm, are you looking at a monthly budget of around {proposed}?"
                elif field == "move_in_date":
                    return f"Could you please confirm if your move-in date is around {proposed}?"
            return f"Could you please clarify your {field.replace('_', ' ')}?"

        return FALLBACK_QUESTIONS.get(
            field, f"Could you share your {field.replace('_', ' ')}?"
        )

    async def generate_next_question(
        self,
        lead_id: uuid.UUID,
        collect_optional: bool = False,
        actor_id: str = "system",
    ) -> NextQuestionResponse:
        """
        Determines next question, renders natural wording via AIOrchestrator,
        enforces fallback safety, tracks the question event, and returns NextQuestionResponse.
        DOES NOT SEND ANY WHATSAPP MESSAGE.
        """
        lead = self._get_lead_or_404(lead_id)
        req = self._get_requirement_or_404(lead_id)
        rule = self.rule_repo.get_active_rule()

        completed, missing, clarification, completion_pct = self.calculate_field_states(req, rule)
        instruction = self.get_next_question_instruction(lead_id, collect_optional=collect_optional)

        # Audit missing fields calculation
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="MISSING_FIELDS_CALCULATED",
                entity_type="TenantRequirement",
                entity_id=str(req.id),
                new_value={
                    "completed": completed,
                    "missing": missing,
                    "clarification": clarification,
                    "completion_pct": completion_pct,
                },
            )
        )

        # Handle NO_QUESTION and HUMAN_REVIEW
        if instruction.action in (QuestionAction.NO_QUESTION, QuestionAction.HUMAN_REVIEW):
            if instruction.action == QuestionAction.HUMAN_REVIEW:
                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="HUMAN_REVIEW_REQUESTED",
                        entity_type="Lead",
                        entity_id=str(lead.id),
                        new_value={"reason": instruction.reason, "context": instruction.context},
                    )
                )

            return NextQuestionResponse(
                lead_id=lead_id,
                action=instruction.action,
                field=instruction.field,
                question_type=instruction.question_type,
                question_text=None,
                fallback_used=False,
                reason=instruction.reason,
                completion_percentage=completion_pct,
                completed_fields=completed,
                missing_fields=missing,
                clarification_fields=clarification,
            )

        # Idempotency check: see if a question for this exact field is already GENERATED
        existing_q = self.question_repo.get_active_generated_question(lead_id, instruction.field)
        if existing_q and existing_q.question_text:
            return NextQuestionResponse(
                lead_id=lead_id,
                action=instruction.action,
                field=instruction.field,
                question_type=instruction.question_type,
                question_text=existing_q.question_text,
                fallback_used=False,
                reason=instruction.reason,
                completion_percentage=completion_pct,
                completed_fields=completed,
                missing_fields=missing,
                clarification_fields=clarification,
            )

        # Phrase natural question via AIOrchestrator
        target_field = instruction.field
        question_text = self.get_fallback_question(target_field, instruction.question_type, instruction.context)
        fallback_used = False

        # Build AI context
        ai_ctx = QualificationAIContext(
            lead_id=lead_id,
            tenant_requirements={
                "preferred_locations": req.preferred_locations,
                "budget_max": float(req.budget_max) if req.budget_max else None,
                "property_type": req.property_type,
                "bedrooms": req.bedrooms,
                "move_in_date": req.move_in_date.isoformat() if req.move_in_date else None,
                "lease_duration_months": req.lease_duration_months,
                "occupants": req.occupants,
            },
            missing_required_fields=missing,
            recent_messages=[
                NormalizedMessage(
                    role=MessageRole.AI,
                    text=f"Target field: {target_field}, Question type: {instruction.question_type}",
                )
            ],
        )

        try:
            ai_resp = await self.orchestrator.execute_structured(
                task_type=AITaskType.RESPONSE_GENERATION,
                context=ai_ctx,
                response_model=QuestionResponseResult,
                custom_prompt=(
                    f"Target Field: {target_field}\n"
                    f"Question Type: {instruction.question_type}\n"
                    f"Question Context: {instruction.context}\n"
                ),
                db=self.db,
            )
            result_data: QuestionResponseResult = ai_resp.data

            # Target field validation: AI must not change the question target
            if result_data.target_field == target_field and result_data.reply_text.strip():
                question_text = result_data.reply_text.strip()
                fallback_used = False
            else:
                logger.warning(
                    f"AI target_field mismatch (expected '{target_field}', got '{result_data.target_field}'). Using fallback."
                )
                fallback_used = True
                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id="system",
                        action="FALLBACK_QUESTION_USED",
                        entity_type="TenantRequirement",
                        entity_id=str(req.id),
                        new_value={
                            "reason": "target_field_mismatch",
                            "expected": target_field,
                            "received": result_data.target_field,
                        },
                    )
                )
        except Exception as exc:
            logger.warning(f"AI response generation failed: {exc}. Using fallback question.")
            fallback_used = True
            self.audit_repo.log(
                AuditLogCreate(
                    actor_id="system",
                    action="FALLBACK_QUESTION_USED",
                    entity_type="TenantRequirement",
                    entity_id=str(req.id),
                    new_value={"reason": "ai_exception", "error": str(exc)},
                )
            )

        # Store question event in database
        self.question_repo.create(
            lead_id=lead_id,
            action=instruction.action,
            question_type=instruction.question_type or QuestionType.MISSING_FIELD,
            field_name=target_field,
            question_text=question_text,
            reason=instruction.reason,
            context_data=instruction.context,
            source="AI" if not fallback_used else "FALLBACK",
            prompt_version="qualification_question_v1",
            clarification_attempts=instruction.context.get("attempts", 0),
            status=QualificationQuestionStatus.GENERATED,
        )

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="QUESTION_GENERATED",
                entity_type="Lead",
                entity_id=str(lead.id),
                new_value={
                    "field": target_field,
                    "action": instruction.action.value,
                    "fallback_used": fallback_used,
                    "question_text": question_text,
                },
            )
        )

        return NextQuestionResponse(
            lead_id=lead_id,
            action=instruction.action,
            field=target_field,
            question_type=instruction.question_type,
            question_text=question_text,
            fallback_used=fallback_used,
            reason=instruction.reason,
            completion_percentage=completion_pct,
            completed_fields=completed,
            missing_fields=missing,
            clarification_fields=clarification,
        )

    def preview_qualification(self, lead_id: uuid.UUID) -> QualificationPreviewResponse:
        """
        Lightweight preview endpoint for frontend visualization.
        Does not invoke LLM or create database events.
        """
        self._get_lead_or_404(lead_id)
        req = self._get_requirement_or_404(lead_id)
        rule = self.rule_repo.get_active_rule()

        completed, missing, clarification, completion_pct = self.calculate_field_states(req, rule)
        instruction = self.get_next_question_instruction(lead_id)

        next_q_data = None
        if instruction.action in (QuestionAction.ASK_FIELD, QuestionAction.ASK_CLARIFICATION):
            fallback = self.get_fallback_question(
                instruction.field, instruction.question_type, instruction.context
            )
            next_q_data = {
                "action": instruction.action.value,
                "field": instruction.field,
                "question_type": instruction.question_type.value if instruction.question_type else None,
                "reason": instruction.reason,
                "preview_text": fallback,
            }
        elif instruction.action == QuestionAction.HUMAN_REVIEW:
            next_q_data = {
                "action": instruction.action.value,
                "field": instruction.field,
                "reason": instruction.reason,
            }
        else:
            next_q_data = {
                "action": instruction.action.value,
                "reason": instruction.reason,
            }

        return QualificationPreviewResponse(
            lead_id=lead_id,
            completion_percentage=completion_pct,
            completed_fields=completed,
            missing_fields=missing,
            clarification_fields=clarification,
            next_question=next_q_data,
        )
