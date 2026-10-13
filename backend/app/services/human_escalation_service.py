import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models.conversation_escalation import ConversationEscalation
from app.models.tenant_requirement import TenantRequirement
from app.models.enums import (
    EscalationStatus,
    EscalationReason,
    QualificationStatus,
    QualificationMode,
    MessageDirection,
    MessageType,
)
from app.repositories.lead_repo import LeadRepository
from app.repositories.tenant_requirement_repo import TenantRequirementRepository
from app.repositories.conversation_escalation_repo import ConversationEscalationRepository
from app.repositories.audit_repo import AuditRepository
from app.repositories.message_repo import MessageRepository
from app.schemas.audit import AuditLogCreate
from app.schemas.escalation import EscalationResponse
from app.services.whatsapp_service import WhatsAppService


class HumanEscalationService:
    """
    Module 3 Phase 7: Human Escalation & Takeover Service.
    Coordinates transition from AI autonomy to human operator intervention,
    ensuring AI is safely paused, messages are properly attributed,
    and returning to AI recalculates state without losing qualification progress.
    """

    ACKNOWLEDGMENT_MESSAGE = "I'll have a team member assist you with this shortly."

    def __init__(self, db: Session, wa_service: Optional[WhatsAppService] = None):
        self.db = db
        self.lead_repo = LeadRepository(db)
        self.req_repo = TenantRequirementRepository(db)
        self.escalation_repo = ConversationEscalationRepository(db)
        self.audit_repo = AuditRepository(db)
        self.msg_repo = MessageRepository(db)
        self.wa_service = wa_service or WhatsAppService(db)

    def escalate(
        self,
        lead_id: uuid.UUID,
        reason_code: EscalationReason,
        description: Optional[str] = None,
        created_by: str = "system",
        send_ack: bool = False,
    ) -> EscalationResponse:
        """
        Escalates a lead to human review, pauses AI qualification, and updates states.
        """
        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found.")

        # Check for existing open escalation
        existing = self.escalation_repo.get_latest_open_for_lead(lead_id)
        if existing:
            return EscalationResponse.model_validate(existing)

        # 1. Pause AI and update qualification status
        req = self.req_repo.get_by_lead_id(lead_id)
        if req:
            req.ai_paused = True
            req.qualification_status = QualificationStatus.NEEDS_HUMAN_REVIEW
            self.db.commit()

        # 2. Create escalation record
        escalation = self.escalation_repo.create({
            "lead_id": lead_id,
            "reason_code": reason_code,
            "description": description,
            "status": EscalationStatus.OPEN,
            "created_by": created_by,
        })

        # 3. Audit events
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=created_by,
                action="HUMAN_REVIEW_REQUESTED",
                entity_type="ConversationEscalation",
                entity_id=str(escalation.id),
                new_value={
                    "lead_id": str(lead_id),
                    "reason_code": reason_code.value,
                    "description": description,
                },
            )
        )
        self.audit_repo.log(
            AuditLogCreate(
                actor_id=created_by,
                action="AI_PAUSED",
                entity_type="Lead",
                entity_id=str(lead_id),
                new_value={"reason": "escalation_opened"},
            )
        )

        # 4. Optional acknowledgment outbound message
        if send_ack and lead.assigned_whatsapp_profile_id:
            try:
                self.wa_service.send_message(
                    profile_id=lead.assigned_whatsapp_profile_id,
                    recipient=lead.phone_normalized,
                    content=self.ACKNOWLEDGMENT_MESSAGE,
                    actor_id=created_by,
                )
            except Exception as e:
                # Log send exception but do not fail escalation
                pass

        return EscalationResponse.model_validate(escalation)

    def take_over(
        self,
        lead_id: uuid.UUID,
        operator_id: str,
    ) -> EscalationResponse:
        """
        Operator assumes active control of the conversation.
        Transitions AI to HUMAN_TAKEOVER mode and assigns escalation.
        """
        if not operator_id or not operator_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Operator ID is required.")

        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found.")

        # Find or create escalation
        escalation = self.escalation_repo.get_latest_open_for_lead(lead_id)
        if not escalation:
            # Create operator-initiated escalation
            escalation_rec = self.escalation_repo.create({
                "lead_id": lead_id,
                "reason_code": EscalationReason.OPERATOR_TAKEOVER,
                "description": f"Manual takeover by operator {operator_id}",
                "status": EscalationStatus.ASSIGNED,
                "assigned_to": operator_id,
                "created_by": operator_id,
            })
            escalation = escalation_rec
        else:
            escalation = self.escalation_repo.update(
                escalation,
                {"status": EscalationStatus.ASSIGNED, "assigned_to": operator_id},
            )

        # Ensure AI paused
        req = self.req_repo.get_by_lead_id(lead_id)
        if req:
            req.ai_paused = True
            self.db.commit()

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=operator_id,
                action="OPERATOR_TAKEOVER",
                entity_type="Lead",
                entity_id=str(lead_id),
                new_value={"operator_id": operator_id, "escalation_id": str(escalation.id)},
            )
        )

        return EscalationResponse.model_validate(escalation)

    def send_operator_message(
        self,
        lead_id: uuid.UUID,
        operator_id: str,
        content: str,
    ) -> Dict[str, Any]:
        """
        Sends an outbound message attributable strictly to the human operator.
        """
        if not operator_id or not operator_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Operator ID is required.")
        if not content or not content.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty.")

        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found.")
        if not lead.assigned_whatsapp_profile_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Lead has no assigned WhatsApp profile.")

        # Send via WhatsAppService
        msg = self.wa_service.send_message(
            profile_id=lead.assigned_whatsapp_profile_id,
            recipient=lead.phone_normalized,
            content=content.strip(),
            actor_id=operator_id,
        )

        # Tag raw_payload with human attribution
        payload = msg.raw_payload or {}
        payload["sender_type"] = "HUMAN_OPERATOR"
        payload["operator_id"] = operator_id
        msg.raw_payload = payload
        self.db.commit()

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=operator_id,
                action="HUMAN_MESSAGE_SENT",
                entity_type="WhatsAppMessage",
                entity_id=str(msg.id),
                new_value={"lead_id": str(lead_id), "operator_id": operator_id, "content_length": len(content)},
            )
        )

        return {
            "message_id": str(msg.id),
            "status": "sent",
            "sender_type": "HUMAN_OPERATOR",
            "operator_id": operator_id,
        }

    def return_to_ai(
        self,
        lead_id: uuid.UUID,
        operator_id: str,
        resolution_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolves open escalations, recalculates current qualification requirements and missing fields,
        unpauses AI qualification, and resumes qualification from current state.
        """
        if not operator_id or not operator_id.strip():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Operator ID is required.")

        lead = self.lead_repo.get_by_id(lead_id)
        if not lead:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Lead '{lead_id}' not found.")

        # 1. Resolve open escalation
        open_escalation = self.escalation_repo.get_latest_open_for_lead(lead_id)
        if open_escalation:
            self.escalation_repo.resolve(open_escalation, resolution_notes=resolution_notes)
            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=operator_id,
                    action="ESCALATION_RESOLVED",
                    entity_type="ConversationEscalation",
                    entity_id=str(open_escalation.id),
                    new_value={"resolution_notes": resolution_notes},
                )
            )

        # 2. Recalculate qualification state
        from app.services.qualification_decision_service import QualificationDecisionService
        decision_service = QualificationDecisionService(self.db)
        eval_res = decision_service.evaluate_qualification(lead_id, apply=True, actor_id=operator_id)

        # 3. Unpause AI on requirements profile
        req = self.req_repo.get_by_lead_id(lead_id)
        if req:
            req.ai_paused = False
            self.db.commit()

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=operator_id,
                action="AI_RESUMED",
                entity_type="Lead",
                entity_id=str(lead_id),
                new_value={"qualification_status": req.qualification_status.value if req else "UNKNOWN"},
            )
        )

        # 4. Refresh conversation summary to reflect post-takeover state
        from app.services.qualification_memory_service import QualificationMemoryService
        from app.models.enums import SummaryGeneratedBy
        memory_service = QualificationMemoryService(self.db)
        det_text, det_structured = memory_service.build_deterministic_summary(lead_id)
        memory_service.summary_repo.create({
            "lead_id": lead_id,
            "summary_text": det_text,
            "structured_summary": det_structured,
            "generated_by": SummaryGeneratedBy.HUMAN,
        })

        return {
            "status": "resumed",
            "lead_id": str(lead_id),
            "ai_paused": False,
            "qualification_status": req.qualification_status.value if req else None,
            "completion_percentage": eval_res.completion_percentage,
            "decision": eval_res.decision.value,
        }
