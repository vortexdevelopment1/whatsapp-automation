import uuid
import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.message import WhatsAppMessage
from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.models.qualification_question import QualificationQuestion
from app.models.message_ai_processing import MessageAIProcessing
from app.models.enums import (
    MessageDirection,
    LeadStatus,
    ConsentStatus,
    OptOutStatus,
    QualificationStatus,
    QuestionAction,
    QualificationQuestionStatus,
    MessageAIProcessingStatus,
    EscalationStatus,
    EscalationReason,
)
from app.ai.enums import TenantIntent
from app.core.locks import conversation_lock_manager
from app.repositories.lead_repo import LeadRepository
from app.repositories.tenant_requirement_repo import TenantRequirementRepository
from app.repositories.message_ai_processing_repo import MessageAIProcessingRepository
from app.repositories.qualification_question_repo import QualificationQuestionRepository
from app.repositories.conversation_escalation_repo import ConversationEscalationRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from app.services.tenant_message_understanding_service import TenantMessageUnderstandingService
from app.services.qualification_question_service import QualificationQuestionService
from app.services.qualification_decision_service import QualificationDecisionService
from app.services.faq_service import FAQService
from app.services.human_escalation_service import HumanEscalationService
from app.services.whatsapp_service import WhatsAppService
from app.ai.orchestrator import AIOrchestrator

logger = logging.getLogger(__name__)


class QualificationConversationProcessor:
    """
    End-to-end live WhatsApp qualification processor.
    Takes an inbound tenant message, acquires conversation lock, extracts requirements,
    evaluates missing fields, determines next action, and sends reply via WhatsAppService.
    """

    def __init__(self, db: Session, orchestrator: Optional[AIOrchestrator] = None):
        self.db = db
        self.orchestrator = orchestrator or AIOrchestrator()
        self.lead_repo = LeadRepository(db)
        self.req_repo = TenantRequirementRepository(db)
        self.processing_repo = MessageAIProcessingRepository(db)
        self.question_repo = QualificationQuestionRepository(db)
        self.escalation_repo = ConversationEscalationRepository(db)
        self.audit_repo = AuditRepository(db)
        self.wa_service = WhatsAppService(db)
        self.understanding_service = TenantMessageUnderstandingService(db, self.orchestrator)
        self.question_service = QualificationQuestionService(db, self.orchestrator)
        self.decision_service = QualificationDecisionService(db)
        self.faq_service = FAQService(db)
        self.escalation_service = HumanEscalationService(db, self.wa_service)

    async def process_message(
        self,
        message_id: uuid.UUID,
        lead_id: Optional[uuid.UUID] = None,
        force_retry: bool = False,
        actor_id: str = "system",
    ) -> Dict[str, Any]:
        """
        Process a single inbound WhatsApp tenant message idempotently with conversation locking.
        """
        # 1. Load inbound message
        msg = self.db.query(WhatsAppMessage).filter(WhatsAppMessage.id == message_id).first()
        if not msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"WhatsAppMessage with ID '{message_id}' not found.",
            )

        if msg.direction != MessageDirection.INBOUND:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Only INBOUND messages from tenants can be processed by qualification processor.",
            )

        # 2. Resolve lead
        lead = None
        if lead_id:
            lead = self.lead_repo.get_by_id(lead_id)
        elif msg.sender:
            lead = self.lead_repo.get_by_phone_normalized(msg.sender)

        if not lead:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Cannot associate message '{message_id}' with any registered lead.",
            )

        # 3. Eligibility checks
        if lead.status == LeadStatus.ARCHIVED:
            logger.info(f"Lead {lead.id} is ARCHIVED. Skipping automated qualification.")
            return {"status": "skipped", "reason": "lead_archived", "lead_id": str(lead.id), "outbound_sent": False}

        if lead.opt_out_status == OptOutStatus.OPTED_OUT or lead.consent_status == ConsentStatus.NOT_CONSENTED:
            logger.info(f"Lead {lead.id} has opted out. Skipping automated qualification.")
            return {"status": "skipped", "reason": "lead_opted_out", "lead_id": str(lead.id), "outbound_sent": False}

        # 4. Check if tenant requirements exist, or create default
        req = self.req_repo.get_by_lead_id(lead.id)
        if not req:
            req = TenantRequirement(
                lead_id=lead.id,
                qualification_status=QualificationStatus.NOT_STARTED,
                completion_percentage=0,
                ai_paused=False,
            )
            self.db.add(req)
            self.db.commit()
            self.db.refresh(req)

        # 5. Check if AI qualification is paused or in human takeover
        open_esc = self.escalation_repo.get_latest_open_for_lead(lead.id)
        if (req.ai_paused or (open_esc and open_esc.status in (EscalationStatus.OPEN, EscalationStatus.ASSIGNED))) and not force_retry:
            logger.info(f"AI qualification is PAUSED/TAKEOVER for lead {lead.id}. Recording message without automated reply.")
            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action="AI_QUALIFICATION_PAUSED_SKIPPED",
                    entity_type="Lead",
                    entity_id=str(lead.id),
                    new_value={"message_id": str(msg.id)},
                )
            )
            return {
                "status": "blocked",
                "reason": "AI qualification is paused or in human takeover",
                "lead_id": str(lead.id),
                "outbound_sent": False,
            }

        # 6. Acquire conversation lock for this lead
        acquired = await conversation_lock_manager.acquire(lead.id, timeout=2.0)
        if not acquired:
            logger.warning(f"Could not acquire conversation lock for lead {lead.id}")
            return {
                "status": "locked",
                "reason": "lock_timeout",
                "lead_id": str(lead.id),
                "outbound_sent": False,
            }

        try:
            # 7. Idempotency check: see if response was already generated & sent for this inbound message
            existing_proc = self.processing_repo.get_by_message_id(msg.id)
            if existing_proc and not force_retry:
                if existing_proc.response_message_id:
                    logger.info(f"Message {msg.id} already processed with outbound reply {existing_proc.response_message_id}.")
                    return {
                        "status": "already_processed",
                        "lead_id": str(lead.id),
                        "message_id": str(msg.id),
                        "response_message_id": str(existing_proc.response_message_id),
                        "outbound_sent": True,
                    }
                elif existing_proc.status in (
                    MessageAIProcessingStatus.PROCESSED,
                    MessageAIProcessingStatus.NEEDS_CLARIFICATION,
                ):
                    existing_outbound = (
                        self.db.query(WhatsAppMessage)
                        .filter(
                            WhatsAppMessage.direction == MessageDirection.OUTBOUND,
                            WhatsAppMessage.raw_payload["reply_to_message_id"].astext == str(msg.id),
                        )
                        .first()
                    )
                    if existing_outbound:
                        return {
                            "status": "already_processed",
                            "lead_id": str(lead.id),
                            "message_id": str(msg.id),
                            "response_message_id": str(existing_outbound.id),
                            "outbound_sent": True,
                        }

            # 8. Transition qualification status to QUALIFYING if initial
            if req.qualification_status in (QualificationStatus.NOT_STARTED, QualificationStatus.WAITING_FOR_TENANT):
                req.qualification_status = QualificationStatus.QUALIFYING
                self.db.commit()

            # 9. Execute message understanding (intent classification + requirement extraction)
            try:
                understanding = await self.understanding_service.process_tenant_message(msg.id, lead.id, actor_id=actor_id)
            except Exception as exc:
                logger.error(f"Message understanding failed for message {msg.id}: {exc}")
                proc_rec = self.processing_repo.get_by_message_id(msg.id)
                if not proc_rec:
                    proc_rec = MessageAIProcessing(
                        message_id=msg.id,
                        lead_id=lead.id,
                        status=MessageAIProcessingStatus.FAILED,
                        error_message=str(exc),
                    )
                    self.db.add(proc_rec)
                    self.db.commit()
                else:
                    proc_rec.status = MessageAIProcessingStatus.FAILED
                    proc_rec.error_message = str(exc)
                    self.db.commit()
                return {
                    "status": "failed",
                    "error": str(exc),
                    "lead_id": str(lead.id),
                    "outbound_sent": False,
                }

            # Re-fetch requirement after understanding update
            self.db.refresh(req)

            # 10. Handle special intents: ASK_FOR_HUMAN, ASK_FAQ, STOP_CONVERSATION
            if understanding.intent == TenantIntent.ASK_FOR_HUMAN:
                self.escalation_service.escalate(
                    lead_id=lead.id,
                    reason_code=EscalationReason.TENANT_REQUESTED_HUMAN,
                    description="Tenant requested to speak with a human",
                    send_ack=False,
                )
                return {
                    "status": "human_review",
                    "reason": "tenant_requested_human",
                    "lead_id": str(lead.id),
                    "intent": TenantIntent.ASK_FOR_HUMAN.value,
                    "outbound_sent": False,
                }

            if understanding.intent == TenantIntent.ASK_FAQ:
                match_res = self.faq_service.match_faq(msg.content or "", actor_id=actor_id)
                if match_res.matched and match_res.faq:
                    faq_answer = match_res.faq.answer
                    # Preserve qualification context: determine next question if qualification incomplete
                    next_q = await self.question_service.generate_next_question(lead.id, actor_id=actor_id)
                    if next_q.action in (QuestionAction.ASK_FIELD, QuestionAction.ASK_CLARIFICATION):
                        q_text = (next_q.question_text or "").strip() or self.question_service.get_fallback_question(next_q.field, next_q.question_type, {})
                        reply_text = f"{faq_answer}\n\nRegarding your search: {q_text}"
                    else:
                        reply_text = faq_answer

                    # Send response via WhatsAppService
                    outbound_idempotency_key = f"qualification:{lead.id}:{msg.id}:faq"
                    try:
                        outbound_msg = self.wa_service.send_message(
                            profile_id=msg.whatsapp_profile_id,
                            recipient=lead.phone_normalized,
                            content=reply_text,
                            idempotency_key=outbound_idempotency_key,
                            reply_to_message_id=msg.id,
                            actor_id=actor_id,
                        )
                        self.audit_repo.log(
                            AuditLogCreate(
                                actor_id=actor_id,
                                action="FAQ_RESPONSE_SENT",
                                entity_type="WhatsAppMessage",
                                entity_id=str(outbound_msg.id),
                                new_value={"lead_id": str(lead.id), "faq_id": str(match_res.faq.id)},
                            )
                        )
                        return {
                            "status": "faq_answered",
                            "lead_id": str(lead.id),
                            "faq_id": str(match_res.faq.id),
                            "question": reply_text,
                            "outbound_sent": True,
                            "outbound_message_id": str(outbound_msg.id),
                        }
                    except Exception as e:
                        logger.error(f"Failed to send FAQ response to lead {lead.id}: {e}")
                        return {
                            "status": "failed",
                            "lead_id": str(lead.id),
                            "error": str(e),
                            "outbound_sent": False,
                        }
                else:
                    # Safe fallback - do NOT hallucinate!
                    fallback_reply = match_res.fallback_message or self.faq_service.FALLBACK_MESSAGE
                    self.escalation_service.escalate(
                        lead_id=lead.id,
                        reason_code=EscalationReason.UNSUPPORTED_FAQ,
                        description=f"Unsupported question: {msg.content}",
                        send_ack=False,
                    )
                    outbound_idempotency_key = f"qualification:{lead.id}:{msg.id}:faq_fallback"
                    try:
                        outbound_msg = self.wa_service.send_message(
                            profile_id=msg.whatsapp_profile_id,
                            recipient=lead.phone_normalized,
                            content=fallback_reply,
                            idempotency_key=outbound_idempotency_key,
                            reply_to_message_id=msg.id,
                            actor_id=actor_id,
                        )
                        return {
                            "status": "faq_not_found_escalated",
                            "lead_id": str(lead.id),
                            "question": fallback_reply,
                            "outbound_sent": True,
                            "outbound_message_id": str(outbound_msg.id),
                        }
                    except Exception as e:
                        logger.error(f"Failed to send FAQ fallback to lead {lead.id}: {e}")
                        return {
                            "status": "failed",
                            "lead_id": str(lead.id),
                            "error": str(e),
                            "outbound_sent": False,
                        }

            if understanding.intent == TenantIntent.STOP_CONVERSATION:
                req.ai_paused = True
                self.db.commit()
                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="QUALIFICATION_STOPPED_BY_TENANT",
                        entity_type="Lead",
                        entity_id=str(lead.id),
                        new_value={"message_id": str(msg.id)},
                    )
                )
                return {
                    "status": "conversation_stopped",
                    "lead_id": str(lead.id),
                    "intent": TenantIntent.STOP_CONVERSATION.value,
                    "outbound_sent": False,
                }

            # 11. Determine next action via Question Engine
            next_q = await self.question_service.generate_next_question(lead.id, actor_id=actor_id)

            # Case: NO_QUESTION -> All required fields complete!
            if next_q.action == QuestionAction.NO_QUESTION:
                req.qualification_status = QualificationStatus.QUALIFICATION_COMPLETE
                self.db.commit()

                # Phase 6: Run deterministic qualification decision layer
                decision_res = self.decision_service.evaluate_qualification(
                    lead_id=lead.id,
                    apply=True,
                    actor_id=actor_id,
                )

                return {
                    "status": "processed",
                    "lead_id": str(lead.id),
                    "qualification_decision": decision_res.decision.value,
                    "decision_reasons": decision_res.reason_codes,
                    "completion_percentage": decision_res.completion_percentage,
                    "completed_fields": next_q.completed_fields,
                    "action": QuestionAction.NO_QUESTION.value,
                    "intent": understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent),
                    "outbound_sent": False,
                }

            # Case: HUMAN_REVIEW
            if next_q.action == QuestionAction.HUMAN_REVIEW:
                reason_code = (
                    EscalationReason.MAX_CLARIFICATION_EXCEEDED
                    if "clarification" in (next_q.reason or "").lower()
                    else EscalationReason.QUALIFICATION_NEEDS_REVIEW
                )
                self.escalation_service.escalate(
                    lead_id=lead.id,
                    reason_code=reason_code,
                    description=next_q.reason,
                    send_ack=True,
                )
                return {
                    "status": "human_review",
                    "reason": next_q.reason,
                    "lead_id": str(lead.id),
                    "action": QuestionAction.HUMAN_REVIEW.value,
                    "intent": understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent),
                    "outbound_sent": True,
                }

            # Case: ASK_FIELD or ASK_CLARIFICATION -> Send Reply via WhatsAppService
            reply_text = (next_q.question_text or "").strip()
            if not reply_text:
                reply_text = self.question_service.get_fallback_question(next_q.field, next_q.question_type, {})

            # 12. Outbound Idempotency Check & Send
            # Concurrency check right before sending: Ensure human takeover has not started
            open_esc = self.escalation_repo.get_latest_open_for_lead(lead.id)
            if req.ai_paused or (open_esc and open_esc.status in (EscalationStatus.OPEN, EscalationStatus.ASSIGNED)):
                logger.info(f"Human takeover active for lead {lead.id}, aborting AI outbound send.")
                return {
                    "status": "blocked",
                    "reason": "human_takeover_active",
                    "lead_id": str(lead.id),
                    "outbound_sent": False,
                }

            outbound_idempotency_key = f"qualification:{lead.id}:{msg.id}:response"

            try:
                outbound_msg = self.wa_service.send_message(
                    profile_id=msg.whatsapp_profile_id,
                    recipient=lead.phone_normalized,
                    content=reply_text,
                    idempotency_key=outbound_idempotency_key,
                    reply_to_message_id=msg.id,
                    actor_id=actor_id,
                )
                outbound_sent = True
                send_error = None
            except Exception as send_exc:
                logger.error(f"WhatsApp send failed for lead {lead.id}: {send_exc}")
                outbound_msg = None
                outbound_sent = False
                send_error = str(send_exc)

            if outbound_sent and outbound_msg:
                # 13. Update qualification state & records
                req.qualification_status = QualificationStatus.WAITING_FOR_TENANT
                self.db.commit()

                # Correlate outbound response message in MessageAIProcessing record
                proc_record = self.processing_repo.get_by_message_id(msg.id)
                if proc_record:
                    self.processing_repo.update_response_message(proc_record.id, outbound_msg.id)

                # Update question event in qualification_questions to SENT
                active_q = (
                    self.db.query(QualificationQuestion)
                    .filter(
                        QualificationQuestion.lead_id == lead.id,
                        QualificationQuestion.field_name == next_q.field,
                        QualificationQuestion.status == QualificationQuestionStatus.GENERATED,
                    )
                    .order_by(QualificationQuestion.created_at.desc())
                    .first()
                )
                if active_q:
                    active_q.status = QualificationQuestionStatus.SENT
                    active_q.message_id = outbound_msg.id
                    self.db.commit()

                self.audit_repo.log(
                    AuditLogCreate(
                        actor_id=actor_id,
                        action="QUALIFICATION_QUESTION_SENT",
                        entity_type="WhatsAppMessage",
                        entity_id=str(outbound_msg.id),
                        new_value={
                            "lead_id": str(lead.id),
                            "field": next_q.field,
                            "action": next_q.action.value,
                            "question_text": reply_text,
                        },
                    )
                )

                return {
                    "status": "processed",
                    "lead_id": str(lead.id),
                    "inbound_message_id": str(msg.id),
                    "outbound_message_id": str(outbound_msg.id),
                    "question": reply_text,
                    "field": next_q.field,
                    "action": next_q.action.value,
                    "intent": understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent),
                    "completion_percentage": next_q.completion_percentage,
                    "outbound_sent": True,
                }
            else:
                return {
                    "status": "processed",
                    "lead_id": str(lead.id),
                    "inbound_message_id": str(msg.id),
                    "outbound_sent": False,
                    "send_error": send_error,
                    "action": next_q.action.value,
                    "intent": understanding.intent.value if hasattr(understanding.intent, "value") else str(understanding.intent),
                }

        finally:
            await conversation_lock_manager.release(lead.id)
