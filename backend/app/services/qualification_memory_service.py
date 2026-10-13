import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal
from datetime import date, datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.lead import Lead
from app.models.message import WhatsAppMessage
from app.models.tenant_requirement import TenantRequirement
from app.models.conversation_summary import ConversationSummary
from app.models.enums import (
    MessageDirection,
    MessageType,
    QualificationStatus,
    QualificationMode,
    AITaskType,
    SummaryGeneratedBy,
    ClarificationStatus,
    EscalationStatus,
)
from app.ai.enums import TenantIntent, MessageRole
from app.ai.schemas import (
    QualificationAIContext,
    NormalizedMessage,
    ConversationSummaryResult,
)
from app.ai.orchestrator import AIOrchestrator
from app.repositories.lead_repo import LeadRepository
from app.repositories.tenant_requirement_repo import TenantRequirementRepository
from app.repositories.qualification_rule_repo import QualificationRuleRepository
from app.repositories.qualification_clarification_repo import QualificationClarificationRepository
from app.repositories.conversation_escalation_repo import ConversationEscalationRepository
from app.repositories.conversation_summary_repo import ConversationSummaryRepository
from app.repositories.conversation_note_repo import ConversationNoteRepository
from app.repositories.qualification_question_repo import QualificationQuestionRepository
from app.repositories.message_ai_processing_repo import MessageAIProcessingRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.memory import (
    StructuredSummary,
    ConversationSummaryResponse,
    ConversationNoteResponse,
    DashboardRequirementField,
    QualificationDashboardResponse,
)
from app.services.qualification_question_service import QualificationQuestionService

logger = logging.getLogger(__name__)


class QualificationMemoryService:
    """
    Module 3 Phase 8: Centralized Conversation Memory, Summary & Dashboard Service.
    
    CORE OPERATIONAL PRINCIPLES:
    1. Structured database state is the absolute source of truth.
    2. Summary is supportive context only and must NEVER override structured criteria.
    3. AI context sends compact relevant messages (bounded by AI_RECENT_MESSAGE_LIMIT)
       rather than full historical message transcripts.
    4. Deterministic summary fallback ensures operators always have reliable context.
    """

    DEFAULT_RECENT_MESSAGE_LIMIT = 10
    MAX_SUMMARY_CHARACTERS = 1500

    def __init__(
        self,
        db: Session,
        orchestrator: Optional[AIOrchestrator] = None,
        recent_message_limit: int = DEFAULT_RECENT_MESSAGE_LIMIT,
    ):
        self.db = db
        self.orchestrator = orchestrator or AIOrchestrator()
        self.recent_message_limit = max(4, min(recent_message_limit, 20))

        self.lead_repo = LeadRepository(db)
        self.req_repo = TenantRequirementRepository(db)
        self.rule_repo = QualificationRuleRepository(db)
        self.clar_repo = QualificationClarificationRepository(db)
        self.esc_repo = ConversationEscalationRepository(db)
        self.summary_repo = ConversationSummaryRepository(db)
        self.note_repo = ConversationNoteRepository(db)
        self.question_repo = QualificationQuestionRepository(db)
        self.proc_repo = MessageAIProcessingRepository(db)
        self.audit_repo = AuditRepository(db)
        self.question_service = QualificationQuestionService(db)

    # =========================================================================
    # 1. MESSAGE FILTERING & WINDOWING
    # =========================================================================

    def get_recent_conversational_messages(
        self, lead_id: uuid.UUID, limit: Optional[int] = None
    ) -> List[WhatsAppMessage]:
        """
        Retrieves recent relevant conversational messages for a lead,
        filtering out technical noise, status pings, and delivery receipts.
        """
        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            return []

        window_size = limit or self.recent_message_limit

        # Query messages where sender or recipient matches lead phone
        query = (
            self.db.query(WhatsAppMessage)
            .filter(
                (WhatsAppMessage.sender == lead.phone_normalized)
                | (WhatsAppMessage.recipient == lead.phone_normalized)
            )
            .filter(WhatsAppMessage.content.isnot(None))
            .filter(WhatsAppMessage.message_type.in_([MessageType.TEXT, MessageType.TEMPLATE]))
            .order_by(desc(WhatsAppMessage.created_at))
            .limit(window_size)
        )
        messages = list(reversed(query.all()))
        return messages

    # =========================================================================
    # 2. COMPACT CONTEXT BUILDER
    # =========================================================================

    def build_ai_context(
        self,
        lead_id: uuid.UUID,
        include_recent_messages: bool = True,
        override_message_limit: Optional[int] = None,
    ) -> QualificationAIContext:
        """
        Builds a compact, token-efficient AI context for qualification tasks.
        Uses structured requirements as source of truth and incorporates
        the latest conversation summary and a bounded window of recent messages.
        """
        lead = self.lead_repo.get_by_id(lead_id)
        req = self.req_repo.get_by_lead_id(lead_id)
        rule = self.rule_repo.get_active_rule()

        qual_status = req.qualification_status.value if req else QualificationStatus.NOT_STARTED.value

        # Structured requirements dictionary (Authoritative)
        structured_reqs: Dict[str, Any] = {}
        if req:
            structured_reqs = {
                "preferred_locations": req.preferred_locations or [],
                "budget_min": float(req.budget_min) if req.budget_min else None,
                "budget_max": float(req.budget_max) if req.budget_max else None,
                "currency": req.currency or "SGD",
                "property_type": req.property_type,
                "bedrooms": req.bedrooms,
                "move_in_date": req.move_in_date.isoformat() if req.move_in_date else None,
                "lease_duration_months": req.lease_duration_months,
                "occupants": req.occupants,
                "furnishing": req.furnishing,
                "special_requirements": req.special_requirements,
            }

        # Calculate field states deterministically
        completed, missing, clarifications, pct = (
            self.question_service.calculate_field_states(req, rule)
            if req
            else ([], list(rule.required_fields or []), [], 0)
        )

        # Load latest summary
        latest_summary = self.summary_repo.get_latest_for_lead(lead_id)
        summary_text = latest_summary.summary_text if latest_summary else None

        # Build bounded recent messages
        normalized_messages: List[NormalizedMessage] = []
        if include_recent_messages:
            limit = override_message_limit or self.recent_message_limit
            raw_msgs = self.get_recent_conversational_messages(lead_id, limit=limit)
            for m in raw_msgs:
                role = MessageRole.TENANT if m.direction == MessageDirection.INBOUND else MessageRole.AI
                normalized_messages.append(
                    NormalizedMessage(
                        role=role,
                        text=m.content or "",
                        message_id=str(m.id),
                        timestamp=m.created_at.isoformat() if m.created_at else None,
                    )
                )

        return QualificationAIContext(
            lead_id=lead_id,
            qualification_status=qual_status,
            tenant_requirements=structured_reqs,
            missing_required_fields=missing,
            conversation_summary=summary_text,
            recent_messages=normalized_messages,
            agent_context={"lead_name": lead.full_name if lead else None},
            route=rule.route if rule else None,
            language="en",
        )

    # =========================================================================
    # 3. DETERMINISTIC SUMMARY BUILDER
    # =========================================================================

    def build_deterministic_summary(self, lead_id: uuid.UUID) -> Tuple[str, Dict[str, Any]]:
        """
        Deterministically builds a human-readable and structured summary
        from validated database records without relying on LLM availability.
        """
        lead = self.lead_repo.get_by_id(lead_id)
        req = self.req_repo.get_by_lead_id(lead_id)
        rule = self.rule_repo.get_active_rule()

        if not req:
            text = "Qualification has not started yet. No requirements recorded."
            return text, StructuredSummary().model_dump()

        completed, missing, clarifications, pct = self.question_service.calculate_field_states(req, rule)

        confirmed_items = []
        if req.preferred_locations:
            confirmed_items.append(f"Location: {', '.join(req.preferred_locations)}")
        if req.budget_max:
            curr = req.currency or "SGD"
            confirmed_items.append(f"Budget: up to {curr} {float(req.budget_max):,.0f}/month")
        if req.property_type and req.property_type != "UNKNOWN":
            confirmed_items.append(f"Type: {req.property_type}")
        if req.bedrooms is not None:
            confirmed_items.append(f"Bedrooms: {req.bedrooms}")
        if req.move_in_date:
            confirmed_items.append(f"Move-in: {req.move_in_date.isoformat()}")
        if req.lease_duration_months:
            confirmed_items.append(f"Lease: {req.lease_duration_months} months")
        if req.occupants:
            confirmed_items.append(f"Occupants: {req.occupants}")
        if req.furnishing and req.furnishing != "UNKNOWN":
            confirmed_items.append(f"Furnishing: {req.furnishing}")

        # Human-readable sentences
        parts = []
        parts.append(f"Qualification is {pct}% complete (status: {req.qualification_status.value.replace('_', ' ')}).")
        if confirmed_items:
            parts.append(f"Confirmed requirements: {'; '.join(confirmed_items)}.")
        else:
            parts.append("No specific rental requirements confirmed yet.")

        if missing:
            clean_missing = [m.replace("_", " ") for m in missing]
            parts.append(f"Still required: {', '.join(clean_missing)}.")

        # Derive mode
        active_esc = self.esc_repo.get_latest_open_for_lead(lead_id)
        if active_esc and active_esc.status in (EscalationStatus.OPEN, EscalationStatus.ASSIGNED):
            derived_mode = QualificationMode.HUMAN_TAKEOVER
        elif req and req.ai_paused:
            derived_mode = QualificationMode.PAUSED
        else:
            derived_mode = QualificationMode.AI_ACTIVE

        if derived_mode == QualificationMode.HUMAN_TAKEOVER:
            parts.append("Currently in HUMAN TAKEOVER mode.")
        elif derived_mode == QualificationMode.PAUSED:
            parts.append("AI qualification is currently PAUSED.")

        summary_text = " ".join(parts)

        structured = StructuredSummary(
            qualification_status=req.qualification_status.value,
            completion_percentage=pct,
            confirmed_requirements={
                "preferred_locations": req.preferred_locations or [],
                "budget_max": float(req.budget_max) if req.budget_max else None,
                "currency": req.currency or "SGD",
                "property_type": req.property_type,
                "bedrooms": req.bedrooms,
                "move_in_date": req.move_in_date.isoformat() if req.move_in_date else None,
                "lease_duration_months": req.lease_duration_months,
                "occupants": req.occupants,
            },
            missing_fields=missing,
            clarifications=clarifications,
            human_review=(derived_mode == QualificationMode.HUMAN_TAKEOVER or (req is not None and req.ai_paused)),
            ai_mode=derived_mode.value,
        ).model_dump()

        return summary_text, structured

    # =========================================================================
    # 4. SUMMARY GENERATION & REFRESH (AI + DETERMINISTIC FALLBACK)
    # =========================================================================

    async def generate_or_refresh_summary(
        self,
        lead_id: uuid.UUID,
        reason: str = "state_change",
        force: bool = False,
        actor_id: str = "system",
    ) -> ConversationSummary:
        """
        Generates or updates the operational conversation summary.
        Uses AIOrchestrator to produce a natural summary, strictly bounded by
        structured requirements, with automatic deterministic fallback.
        """
        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        req = self.req_repo.get_by_lead_id(lead_id)
        rule = self.rule_repo.get_active_rule()
        latest_summary = self.summary_repo.get_latest_for_lead(lead_id)

        # Deterministic foundation
        det_text, det_structured = self.build_deterministic_summary(lead_id)

        ai_summary_text: Optional[str] = None
        structured_summary = det_structured
        generated_by = SummaryGeneratedBy.SYSTEM
        ai_call_id = None
        prompt_version = None

        # Attempt AI generation through AIOrchestrator
        try:
            ctx = self.build_ai_context(lead_id)
            ai_resp = await self.orchestrator.execute_structured(
                task_type=AITaskType.CONVERSATION_SUMMARY,
                context=ctx,
                db=self.db,
            )
            if ai_resp and ai_resp.data:
                data: ConversationSummaryResult = ai_resp.data
                raw_text = (data.summary_text or "").strip()

                # Basic anti-poisoning & consistency sanity check:
                # If budget is confirmed in structured req, check that AI doesn't contradict it
                is_consistent = True
                if req and req.budget_max:
                    curr_budget = float(req.budget_max)
                    # If AI explicitly wrote an old or wrong budget, fall back to deterministic
                    if latest_summary and latest_summary.structured_summary:
                        old_budget = latest_summary.structured_summary.get("confirmed_requirements", {}).get("budget_max")
                        if old_budget and old_budget != curr_budget and str(int(old_budget)) in raw_text:
                            is_consistent = False

                if is_consistent and len(raw_text) > 10:
                    ai_summary_text = raw_text[: self.MAX_SUMMARY_CHARACTERS]
                    generated_by = SummaryGeneratedBy.AI
                    prompt_version = data.prompt_version

        except Exception as exc:
            logger.warning(f"AI conversation summary generation failed for lead '{lead_id}': {exc}. Using deterministic fallback.")

        final_summary_text = ai_summary_text or det_text

        # Create new summary version
        summary_record = self.summary_repo.create({
            "lead_id": lead.id,
            "summary_text": final_summary_text,
            "structured_summary": structured_summary,
            "generated_by": generated_by,
            "ai_call_id": ai_call_id,
            "prompt_version": prompt_version,
        })

        # Audit log
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="CONVERSATION_SUMMARY_GENERATED",
                entity_type="ConversationSummary",
                entity_id=str(summary_record.id),
                new_value={
                    "version": summary_record.summary_version,
                    "reason": reason,
                    "generated_by": generated_by.value,
                },
            )
        )

        return summary_record

    # =========================================================================
    # 5. HUMAN TAKEOVER SYNCHRONIZATION
    # =========================================================================

    async def sync_after_human_takeover(
        self, lead_id: uuid.UUID, actor_id: str = "operator"
    ) -> ConversationSummary:
        """
        Synchronizes conversation state, recalculates requirements,
        and refreshes the summary before AI resumes after a human takeover.
        """
        # Refresh summary from current post-takeover message state
        summary = await self.generate_or_refresh_summary(
            lead_id=lead_id,
            reason="human_takeover_return_to_ai",
            force=True,
            actor_id=actor_id,
        )

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="TAKEOVER_SYNC_COMPLETED",
                entity_type="ConversationSummary",
                entity_id=str(summary.id),
                new_value={"lead_id": str(lead_id), "version": summary.summary_version},
            )
        )
        return summary

    # =========================================================================
    # 6. DASHBOARD AGGREGATE STATE
    # =========================================================================

    def get_qualification_dashboard(self, lead_id: uuid.UUID) -> QualificationDashboardResponse:
        """
        Assembles the authoritative aggregate response for the Qualification Dashboard.
        Combines requirements, field states, progress, clarifications, conflicts,
        latest summary, recent timeline, operator notes, and next action.
        """
        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise ValueError(f"Lead '{lead_id}' not found.")

        req = self.req_repo.get_by_lead_id(lead_id)
        rule = self.rule_repo.get_active_rule()

        # Qualification progress & states
        completed, missing, clarification_fields, pct = (
            self.question_service.calculate_field_states(req, rule)
            if req
            else ([], list(rule.required_fields or []), [], 0)
        )

        # Field-by-field details
        field_details: List[DashboardRequirementField] = []
        all_display_fields = [
            ("preferred_locations", "Preferred Location"),
            ("budget_max", "Budget (Max)"),
            ("property_type", "Property Type"),
            ("bedrooms", "Bedrooms"),
            ("move_in_date", "Move-in Date"),
            ("lease_duration_months", "Lease Duration"),
            ("occupants", "Occupants"),
            ("furnishing", "Furnishing"),
        ]

        # Clarifications
        active_clar_records = self.clar_repo.list_for_lead(lead_id, limit=10)
        clar_dict = {c.field_name: c for c in active_clar_records if c.status in (ClarificationStatus.OPEN, ClarificationStatus.WAITING_FOR_TENANT)}

        # Conflict detection
        conflicts = []
        if req and req.budget_min and req.budget_max and req.budget_min > req.budget_max:
            conflicts.append({
                "field": "budget",
                "description": f"Minimum budget ({req.budget_min}) exceeds maximum budget ({req.budget_max})",
                "status": "UNRESOLVED",
            })

        for field_name, label in all_display_fields:
            val = getattr(req, field_name, None) if req else None
            status_str = "MISSING"
            confidence_level = None
            reason = None

            if field_name in clar_dict:
                status_str = "NEEDS_CLARIFICATION"
                reason = clar_dict[field_name].reason
                confidence_level = "Medium"
            elif field_name in completed:
                status_str = "CONFIRMED"
                confidence_level = "High"
            elif val is not None:
                status_str = "PROPOSED"
                confidence_level = "Medium"
            elif field_name in missing:
                status_str = "MISSING"

            field_details.append(
                DashboardRequirementField(
                    field_name=field_name,
                    label=label,
                    value=val,
                    status=status_str,
                    confidence_level=confidence_level,
                    reason=reason,
                )
            )

        # Active Escalation
        active_esc = self.esc_repo.get_latest_open_for_lead(lead_id)
        active_esc_dict = None
        if active_esc:
            active_esc_dict = {
                "id": str(active_esc.id),
                "reason_code": active_esc.reason_code.value,
                "description": active_esc.description,
                "status": active_esc.status.value,
                "assigned_to": active_esc.assigned_to,
                "created_at": active_esc.created_at.isoformat(),
            }

        # Derive mode
        if active_esc and active_esc.status in (EscalationStatus.OPEN, EscalationStatus.ASSIGNED):
            derived_mode = QualificationMode.HUMAN_TAKEOVER
        elif req and req.ai_paused:
            derived_mode = QualificationMode.PAUSED
        else:
            derived_mode = QualificationMode.AI_ACTIVE

        # Next Expected Action
        next_action_info: Dict[str, Any] = {}
        if req:
            if derived_mode == QualificationMode.HUMAN_TAKEOVER:
                next_action_info = {
                    "action": "HUMAN_TAKEOVER",
                    "label": "Operator Active",
                    "description": "Conversation is being handled by a human operator.",
                }
            elif derived_mode == QualificationMode.PAUSED:
                next_action_info = {
                    "action": "AI_PAUSED",
                    "label": "AI Paused",
                    "description": "Automated messaging is paused awaiting review.",
                }
            elif clarification_fields:
                next_action_info = {
                    "action": "CLARIFICATION",
                    "label": f"Clarify {clarification_fields[0].replace('_', ' ').title()}",
                    "description": f"Awaiting tenant clarification for {clarification_fields[0]}.",
                }
            elif missing:
                next_action_info = {
                    "action": "ASK_FIELD",
                    "label": f"Ask {missing[0].replace('_', ' ').title()}",
                    "description": f"System waiting to collect {missing[0]}.",
                }
            else:
                next_action_info = {
                    "action": "READY_FOR_DECISION",
                    "label": "Ready for Decision",
                    "description": "All required criteria collected. Eligible for qualification evaluation.",
                }

        # Summary
        latest_summary = self.summary_repo.get_latest_for_lead(lead_id)
        summary_resp = ConversationSummaryResponse.model_validate(latest_summary) if latest_summary else None

        # Operator notes
        notes = self.note_repo.list_for_lead(lead_id, limit=20)
        notes_resp = [ConversationNoteResponse.model_validate(n) for n in notes]

        # Recent messages formatted for timeline
        raw_msgs = self.get_recent_conversational_messages(lead_id, limit=12)
        timeline = []
        for m in raw_msgs:
            if m.direction == MessageDirection.INBOUND:
                sender_type = "TENANT"
            elif m.raw_payload and m.raw_payload.get("sender_type") == "HUMAN_OPERATOR":
                sender_type = "HUMAN OPERATOR"
            elif m.raw_payload and m.raw_payload.get("sender_type") == "SYSTEM_EVENT":
                sender_type = "SYSTEM EVENT"
            else:
                sender_type = "AI ASSISTANT"

            timeline.append({
                "id": str(m.id),
                "direction": m.direction.value,
                "sender_type": sender_type,
                "content": m.content,
                "timestamp": m.created_at.isoformat() if m.created_at else None,
                "delivery_status": m.provider_status or "DELIVERED",
            })

        # Last AI Activity
        last_proc = self.proc_repo.get_latest_for_lead(lead_id)
        last_ai_dict = None
        if last_proc:
            last_ai_dict = {
                "intent": last_proc.intent,
                "intent_confidence": float(last_proc.intent_confidence) if last_proc.intent_confidence else None,
                "status": last_proc.status.value if hasattr(last_proc.status, "value") else str(last_proc.status),
                "processed_at": last_proc.processed_at.isoformat() if last_proc.processed_at else None,
                "model": "gpt-4o-mini",
            }

        return QualificationDashboardResponse(
            lead_id=lead.id,
            lead_name=lead.full_name,
            lead_phone=lead.phone_normalized,
            qualification_status=req.qualification_status if req else QualificationStatus.NOT_STARTED,
            completion_percentage=pct,
            ai_mode=derived_mode,
            ai_paused=req.ai_paused if req else False,
            is_human_review=(active_esc is not None or derived_mode == QualificationMode.HUMAN_TAKEOVER),
            requirements={
                "preferred_locations": req.preferred_locations if req else [],
                "budget_max": float(req.budget_max) if req and req.budget_max else None,
                "property_type": req.property_type if req else None,
                "bedrooms": req.bedrooms if req else None,
                "move_in_date": req.move_in_date.isoformat() if req and req.move_in_date else None,
                "lease_duration_months": req.lease_duration_months if req else None,
                "occupants": req.occupants if req else None,
                "furnishing": req.furnishing if req else None,
            },
            field_details=field_details,
            missing_fields=missing,
            clarification_fields=clarification_fields,
            clarifications=[
                {
                    "id": str(c.id),
                    "field_name": c.field_name,
                    "reason": c.reason,
                    "proposed_value": c.proposed_value,
                    "status": c.status.value,
                    "attempt_count": c.attempt_count,
                    "created_at": c.created_at.isoformat(),
                }
                for c in active_clar_records
            ],
            conflicts=conflicts,
            active_escalation=active_esc_dict,
            summary=summary_resp,
            next_action=next_action_info,
            recent_messages=timeline,
            operator_notes=notes_resp,
            last_ai_activity=last_ai_dict,
        )
