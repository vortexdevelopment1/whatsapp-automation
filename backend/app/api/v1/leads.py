import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Header, status, HTTPException
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.models.enums import LeadStatus, ConsentStatus, OptOutStatus, ContactEligibility
from app.schemas.lead import (
    LeadCreate,
    LeadUpdate,
    LeadResponse,
    LeadValidateResponse,
    LeadDuplicateCheckResponse,
    LeadEligibilityCheckResponse,
    LeadDuplicateOverrideRequest,
    LeadMarkOptOutRequest,
    LeadRestoreContactRequest,
)
from app.schemas.lead_routing import LeadRoutingDecisionResponse
from app.schemas.lead_outreach import LeadOutreachResponse
from app.schemas.qualification_decision import QualificationDecisionEvaluateRequest, QualificationDecisionResponse
from app.ai.schemas import NextQuestionResponse, QualificationPreviewResponse
from app.services.lead_service import LeadService

router = APIRouter(prefix="/leads", tags=["leads"])


@router.get("", response_model=List[LeadResponse])
def list_leads(
    status: Optional[LeadStatus] = Query(None, description="Filter by status"),
    source_id: Optional[uuid.UUID] = Query(None, description="Filter by source ID"),
    assigned_agent_id: Optional[uuid.UUID] = Query(None, description="Filter by assigned agent ID"),
    consent_status: Optional[ConsentStatus] = Query(None, description="Filter by consent status"),
    opt_out_status: Optional[OptOutStatus] = Query(None, description="Filter by opt-out status"),
    contact_eligibility: Optional[ContactEligibility] = Query(None, description="Filter by eligibility"),
    search: Optional[str] = Query(None, description="Search by name, phone, or email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.list_leads(
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


@router.post("", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
def create_lead(
    data: LeadCreate,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.create_lead(data)


@router.get("/{lead_id}", response_model=LeadResponse)
def get_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.get_lead_or_404(lead_id)


@router.patch("/{lead_id}", response_model=LeadResponse)
def update_lead(
    lead_id: uuid.UUID,
    data: LeadUpdate,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.update_lead(lead_id, data)


@router.post("/{lead_id}/validate", response_model=LeadValidateResponse)
def validate_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.validate_lead(lead_id)


@router.post("/{lead_id}/archive", response_model=LeadResponse)
def archive_lead(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.archive_lead(lead_id)


@router.get("/{lead_id}/routing-history", response_model=List[LeadRoutingDecisionResponse])
def get_lead_routing_history(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.get_routing_history(lead_id)


@router.get("/{lead_id}/outreach", response_model=List[LeadOutreachResponse])
def get_lead_outreach(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.get_outreach_history(lead_id)


@router.post("/{lead_id}/check-duplicate", response_model=LeadDuplicateCheckResponse)
def check_lead_duplicate(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.check_duplicate(lead_id)


@router.post("/{lead_id}/check-contact-eligibility", response_model=LeadEligibilityCheckResponse)
def check_lead_contact_eligibility(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.check_contact_eligibility(lead_id)


@router.post("/{lead_id}/mark-opt-out", response_model=LeadResponse)
def mark_lead_opt_out(
    lead_id: uuid.UUID,
    body: Optional[LeadMarkOptOutRequest] = None,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    reason = body.reason if body else None
    return service.mark_opt_out(lead_id, reason=reason)


@router.post("/{lead_id}/restore-contact", response_model=LeadResponse)
def restore_lead_contact(
    lead_id: uuid.UUID,
    body: Optional[LeadRestoreContactRequest] = None,
    authorization: Optional[str] = Header(None),
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    reason = body.reason if body else None
    authorized_by = body.authorized_by if body else None
    return service.restore_contact(
        lead_id,
        reason=reason,
        authorized_by=authorized_by,
        authorization_header=authorization,
    )


@router.post("/{lead_id}/duplicate-override", response_model=LeadResponse)
def override_lead_duplicate(
    lead_id: uuid.UUID,
    body: LeadDuplicateOverrideRequest,
    db: Session = Depends(get_db),
):
    service = LeadService(db)
    return service.override_duplicate(lead_id, reason=body.reason)


@router.post("/{lead_id}/messages/{message_id}/analyze")
async def analyze_tenant_message(
    lead_id: uuid.UUID,
    message_id: uuid.UUID,
    x_admin_id: str = Header("operator", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """
    Module 3 Phase 3: Manually or automatically analyze an inbound tenant message,
    classify intent, extract requirements, apply confidence policies, and update
    current tenant search criteria with full provenance.
    NEVER sends WhatsApp replies.
    """
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.tenant_message_understanding_service import TenantMessageUnderstandingService
    service = TenantMessageUnderstandingService(db)
    return await service.process_tenant_message(message_id=message_id, lead_id=lead_id)



@router.get("/{lead_id}/messages/{message_id}/analysis")
def get_tenant_message_analysis(
    lead_id: uuid.UUID,
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve stored AI analysis record for a given message."""
    from app.repositories.message_ai_processing_repo import MessageAIProcessingRepository
    repo = MessageAIProcessingRepository(db)
    record = repo.get_by_message_id(message_id)
    if not record or record.lead_id != lead_id:
        return {"status": "NOT_PROCESSED"}
    return {
        "id": str(record.id),
        "message_id": str(record.message_id),
        "lead_id": str(record.lead_id),
        "intent": record.intent,
        "intent_confidence": float(record.intent_confidence) if record.intent_confidence else None,
        "status": record.status.value if hasattr(record.status, "value") else str(record.status),
        "accepted_fields": record.accepted_fields,
        "proposed_fields": record.proposed_fields,
        "rejected_fields": record.rejected_fields,
        "clarification_fields": record.clarification_fields,
        "raw_extraction": record.raw_extraction,
        "message_summary": record.message_summary,
        "created_at": record.created_at.isoformat(),
    }


@router.post("/{lead_id}/qualification/next-question", response_model=NextQuestionResponse)
async def generate_next_qualification_question(
    lead_id: uuid.UUID,
    collect_optional: bool = Query(False, description="Whether to collect optional fields when all required are satisfied"),
    x_admin_id: str = Header("admin", alias="X-Admin-Id"),
    db: Session = Depends(get_db),
):
    """
    Deterministically identify missing/clarification requirements and generate
    natural language phrasing for the next question via AIOrchestrator.
    DOES NOT send a WhatsApp message.
    """
    from app.services.qualification_question_service import QualificationQuestionService
    service = QualificationQuestionService(db)
    return await service.generate_next_question(
        lead_id=lead_id,
        collect_optional=collect_optional,
        actor_id=x_admin_id,
    )


@router.get("/{lead_id}/qualification/preview", response_model=QualificationPreviewResponse)
def preview_qualification_questions(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Preview completion percentage, completed/missing/clarification fields,
    and next question target without executing LLM calls or persisting events.
    """
    from app.services.qualification_question_service import QualificationQuestionService
    service = QualificationQuestionService(db)
    return service.preview_qualification(lead_id=lead_id)


# Module 3 Phase 5: Live Qualification Conversation Loop Actions

@router.post("/{lead_id}/qualification/process-message/{message_id}")
async def process_qualification_message(
    lead_id: uuid.UUID,
    message_id: uuid.UUID,
    x_admin_id: str = Header("admin", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Trigger the live qualification loop for a specific inbound message."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.qualification_conversation_processor import QualificationConversationProcessor
    processor = QualificationConversationProcessor(db)
    return await processor.process_message(message_id=message_id, lead_id=lead_id, actor_id=x_admin_id)


@router.post("/{lead_id}/qualification/pause")
def pause_ai_qualification(
    lead_id: uuid.UUID,
    x_admin_id: str = Header("admin", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Pause automated AI qualification for a lead (prepare for human takeover)."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.repositories.tenant_requirement_repo import TenantRequirementRepository
    from app.repositories.audit_repo import AuditRepository
    from app.schemas.audit import AuditLogCreate
    from app.models.tenant_requirement import TenantRequirement

    req_repo = TenantRequirementRepository(db)
    req = req_repo.get_by_lead_id(lead_id)
    if not req:
        req = TenantRequirement(lead_id=lead_id, ai_paused=True)
        db.add(req)
        db.commit()
    else:
        req.ai_paused = True
        db.commit()

    AuditRepository(db).log(
        AuditLogCreate(
            actor_id=x_admin_id,
            action="AI_QUALIFICATION_PAUSED",
            entity_type="Lead",
            entity_id=str(lead_id),
            new_value={"ai_paused": True},
        )
    )
    return {"status": "paused", "lead_id": str(lead_id), "ai_paused": True}


@router.post("/{lead_id}/qualification/resume")
def resume_ai_qualification(
    lead_id: uuid.UUID,
    x_admin_id: str = Header("admin", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Resume automated AI qualification for a lead."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.repositories.tenant_requirement_repo import TenantRequirementRepository
    from app.repositories.audit_repo import AuditRepository
    from app.schemas.audit import AuditLogCreate

    req_repo = TenantRequirementRepository(db)
    req = req_repo.get_by_lead_id(lead_id)
    if req:
        req.ai_paused = False
        db.commit()

    AuditRepository(db).log(
        AuditLogCreate(
            actor_id=x_admin_id,
            action="AI_QUALIFICATION_RESUMED",
            entity_type="Lead",
            entity_id=str(lead_id),
            new_value={"ai_paused": False},
        )
    )
    return {"status": "resumed", "lead_id": str(lead_id), "ai_paused": False}


@router.post("/{lead_id}/qualification/retry/{message_id}")
async def retry_qualification_message(
    lead_id: uuid.UUID,
    message_id: uuid.UUID,
    x_admin_id: str = Header("admin", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Force retry qualification processing for a message."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.qualification_conversation_processor import QualificationConversationProcessor
    processor = QualificationConversationProcessor(db)
    return await processor.process_message(message_id=message_id, lead_id=lead_id, force_retry=True, actor_id=x_admin_id)


@router.get("/{lead_id}/qualification/status")
def get_qualification_live_status(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieve full live status of qualification loop for dashboard display."""
    from app.repositories.tenant_requirement_repo import TenantRequirementRepository
    from app.repositories.message_ai_processing_repo import MessageAIProcessingRepository
    from app.repositories.qualification_question_repo import QualificationQuestionRepository
    from app.services.qualification_question_service import QualificationQuestionService
    from app.models.enums import QualificationStatus, QualificationMode, MessageDirection
    from app.models.message import WhatsAppMessage
    from app.models.lead import Lead

    req_repo = TenantRequirementRepository(db)
    proc_repo = MessageAIProcessingRepository(db)
    q_repo = QualificationQuestionRepository(db)

    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    latest_tenant_msg = None
    latest_outbound = None

    if lead and lead.phone_normalized:
        latest_tenant_msg = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.direction == MessageDirection.INBOUND,
                WhatsAppMessage.sender == lead.phone_normalized,
            )
            .order_by(WhatsAppMessage.created_at.desc())
            .first()
        )
        latest_outbound = (
            db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.direction == MessageDirection.OUTBOUND,
                WhatsAppMessage.recipient == lead.phone_normalized,
            )
            .order_by(WhatsAppMessage.created_at.desc())
            .first()
        )

    req = req_repo.get_by_lead_id(lead_id)
    if not req:
        return {
            "lead_id": str(lead_id),
            "qualification_mode": QualificationMode.AI_ACTIVE.value,
            "ai_mode": QualificationMode.AI_ACTIVE.value,
            "ai_paused": False,
            "qualification_status": QualificationStatus.NOT_STARTED.value,
            "completion_percentage": 0,
            "completed_fields": [],
            "missing_fields": [],
            "clarification_fields": [],
            "last_tenant_message": None,
            "last_ai_processing": None,
            "last_outbound_question": None,
            "last_message_analyzed": None,
            "last_question": None,
        }

    q_service = QualificationQuestionService(db)
    completed, missing, clarification, pct = q_service.calculate_field_states(req)

    # Determine AI mode
    if req.ai_paused:
        mode = QualificationMode.PAUSED.value
    elif req.qualification_status == QualificationStatus.NEEDS_HUMAN_REVIEW:
        mode = QualificationMode.HUMAN_REVIEW.value
    else:
        mode = QualificationMode.AI_ACTIVE.value

    latest_proc = proc_repo.get_latest_for_lead(lead_id)
    latest_q = q_repo.get_latest_for_lead(lead_id)

    from app.repositories.qualification_decision_repo import QualificationDecisionRepository
    decision_repo = QualificationDecisionRepository(db)
    latest_dec = decision_repo.get_latest_for_lead(lead_id)

    return {
        "lead_id": str(lead_id),
        "qualification_mode": mode,
        "ai_mode": mode,
        "ai_paused": req.ai_paused,
        "qualification_status": req.qualification_status.value if hasattr(req.qualification_status, "value") else str(req.qualification_status),
        "completion_percentage": pct,
        "completed_fields": completed,
        "missing_fields": missing,
        "clarification_fields": clarification,
        "latest_decision": {
            "id": str(latest_dec.id),
            "decision": latest_dec.decision.value if hasattr(latest_dec.decision, "value") else str(latest_dec.decision),
            "reason_codes": latest_dec.reason_codes,
            "blocking_fields": latest_dec.blocking_fields,
            "rule_version": latest_dec.rule_version,
            "evaluation_source": latest_dec.evaluation_source,
            "evaluated_by": latest_dec.evaluated_by,
            "override_reason": latest_dec.override_reason,
            "created_at": latest_dec.created_at.isoformat() if latest_dec.created_at else None,
        } if latest_dec else None,
        "last_tenant_message": {
            "id": str(latest_tenant_msg.id),
            "content": latest_tenant_msg.content,
            "created_at": latest_tenant_msg.created_at.isoformat() if latest_tenant_msg.created_at else None,
        } if latest_tenant_msg else None,
        "last_ai_processing": {
            "id": str(latest_proc.id),
            "intent": latest_proc.intent,
            "status": latest_proc.status.value if hasattr(latest_proc.status, "value") else str(latest_proc.status),
            "created_at": latest_proc.created_at.isoformat() if latest_proc.created_at else None,
            "completed_at": latest_proc.completed_at.isoformat() if latest_proc.completed_at else None,
            "error_code": latest_proc.error_code,
        } if latest_proc else None,
        "last_outbound_question": {
            "id": str(latest_outbound.id),
            "content": latest_outbound.content,
            "created_at": latest_outbound.created_at.isoformat() if latest_outbound.created_at else None,
        } if latest_outbound else None,
        "last_message_analyzed": {
            "id": str(latest_proc.id),
            "intent": latest_proc.intent,
            "status": latest_proc.status.value if hasattr(latest_proc.status, "value") else str(latest_proc.status),
            "accepted_fields": latest_proc.accepted_fields,
            "proposed_fields": latest_proc.proposed_fields,
        } if latest_proc else None,
        "last_question": {
            "id": str(latest_q.id),
            "field": latest_q.field_name,
            "text": latest_q.question_text,
            "status": latest_q.status.value if hasattr(latest_q.status, "value") else str(latest_q.status),
        } if latest_q else None,
    }


@router.post("/{lead_id}/qualification/evaluate", response_model=QualificationDecisionResponse)
def evaluate_qualification(
    lead_id: uuid.UUID,
    data: Optional[QualificationDecisionEvaluateRequest] = None,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """
    Evaluates qualification decision for lead.
    Supports dry-run preview (apply=False) and state application (apply=True),
    as well as authorized human operator overrides.
    """
    if data and data.override_decision and x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.qualification_decision_service import QualificationDecisionService
    service = QualificationDecisionService(db)
    apply = data.apply if data else False
    override_decision = data.override_decision if data else None
    override_reason = data.override_reason if data else None
    try:
        return service.evaluate_qualification(
            lead_id=lead_id,
            apply=apply,
            actor_id=x_admin_id,
            override_decision=override_decision,
            override_reason=override_reason,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{lead_id}/qualification/decision-history", response_model=List[QualificationDecisionResponse])
def get_qualification_decision_history(
    lead_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """Retrieve decision audit history for a lead."""
    from app.repositories.qualification_decision_repo import QualificationDecisionRepository
    repo = QualificationDecisionRepository(db)
    return repo.list_for_lead(lead_id, limit=limit)


# ==========================================
# MODULE 3 PHASE 7: ESCALATION & HUMAN REVIEW
# ==========================================

@router.get("/human-review-queue")
def get_human_review_queue(
    db: Session = Depends(get_db),
):
    """
    Returns all leads currently in human review or with open/assigned escalations.
    """
    from datetime import datetime, timezone
    from app.models.enums import EscalationStatus, QualificationStatus
    from app.models.lead import Lead
    from app.models.tenant_requirement import TenantRequirement
    from app.models.conversation_escalation import ConversationEscalation
    from app.models.message import WhatsAppMessage
    from app.repositories.qualification_rule_repo import QualificationRuleRepository
    from app.services.tenant_requirement_service import TenantRequirementService

    req_service = TenantRequirementService(db)
    rule = QualificationRuleRepository(db).get_active_rule()

    # Query leads with open escalations or qualification_status == NEEDS_HUMAN_REVIEW
    escalations = (
        db.query(ConversationEscalation)
        .filter(ConversationEscalation.status.in_([EscalationStatus.OPEN, EscalationStatus.ASSIGNED]))
        .order_by(ConversationEscalation.created_at.asc())
        .all()
    )

    escalated_lead_ids = {e.lead_id for e in escalations}

    human_review_reqs = (
        db.query(TenantRequirement)
        .filter(TenantRequirement.qualification_status == QualificationStatus.NEEDS_HUMAN_REVIEW)
        .all()
    )
    for r in human_review_reqs:
        escalated_lead_ids.add(r.lead_id)

    items = []
    now = datetime.now(timezone.utc)

    for lead_id in escalated_lead_ids:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            continue
        req = db.query(TenantRequirement).filter(TenantRequirement.lead_id == lead_id).first()
        esc = (
            db.query(ConversationEscalation)
            .filter(ConversationEscalation.lead_id == lead_id)
            .order_by(ConversationEscalation.created_at.desc())
            .first()
        )
        last_msg = (
            db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.sender == lead.phone_normalized)
            .order_by(WhatsAppMessage.created_at.desc())
            .first()
        )

        missing = req_service.get_missing_required_fields(req, rule) if req else []
        waiting_mins = int((now - (esc.created_at if esc else (req.updated_at if req else now))).total_seconds() / 60)

        items.append({
            "lead_id": str(lead.id),
            "lead_name": f"{lead.first_name or ''} {lead.last_name or ''}".strip() or "Unnamed Lead",
            "phone": lead.phone_normalized,
            "escalation_id": str(esc.id) if esc else None,
            "reason_code": esc.reason_code.value if esc else "needs_human_review",
            "description": esc.description if esc else None,
            "qualification_status": req.qualification_status.value if req else "UNKNOWN",
            "missing_fields": missing,
            "last_message": last_msg.content if last_msg else None,
            "last_message_at": last_msg.created_at.isoformat() if last_msg and last_msg.created_at else None,
            "time_waiting_minutes": max(0, waiting_mins),
            "assigned_to": esc.assigned_to if esc else None,
            "escalation_status": esc.status.value if esc else "OPEN",
            "ai_paused": req.ai_paused if req else False,
        })

    return items


@router.get("/{lead_id}/escalations")
def list_lead_escalations(
    lead_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List escalation history for a lead."""
    from app.repositories.conversation_escalation_repo import ConversationEscalationRepository
    repo = ConversationEscalationRepository(db)
    return repo.list_for_lead(lead_id, limit=limit)


@router.post("/{lead_id}/escalations")
def create_lead_escalation(
    lead_id: uuid.UUID,
    data: Optional[dict] = None,
    x_admin_id: str = Header("system", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Manually escalate a lead to human review."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.human_escalation_service import HumanEscalationService
    from app.models.enums import EscalationReason
    service = HumanEscalationService(db)
    reason_str = data.get("reason_code", EscalationReason.OPERATOR_TAKEOVER.value) if data else EscalationReason.OPERATOR_TAKEOVER.value
    desc = data.get("description") if data else None
    return service.escalate(
        lead_id=lead_id,
        reason_code=EscalationReason(reason_str),
        description=desc,
        created_by=x_admin_id,
        send_ack=True,
    )


@router.post("/{lead_id}/takeover")
def takeover_conversation(
    lead_id: uuid.UUID,
    x_admin_id: str = Header("operator", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Human operator takes over active control of conversation."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.human_escalation_service import HumanEscalationService
    service = HumanEscalationService(db)
    return service.take_over(lead_id, operator_id=x_admin_id)


@router.post("/{lead_id}/operator-message")
def send_operator_message(
    lead_id: uuid.UUID,
    data: dict,
    x_admin_id: str = Header("operator", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Sends an outbound WhatsApp message attributed strictly to the human operator."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    content = data.get("content", "").strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message content cannot be empty.")
    from app.services.human_escalation_service import HumanEscalationService
    service = HumanEscalationService(db)
    return service.send_operator_message(lead_id=lead_id, operator_id=x_admin_id, content=content)


@router.post("/{lead_id}/return-to-ai")
def return_to_ai(
    lead_id: uuid.UUID,
    data: Optional[dict] = None,
    x_admin_id: str = Header("operator", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Resolves escalation, re-evaluates qualification state, and resumes AI."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.human_escalation_service import HumanEscalationService
    service = HumanEscalationService(db)
    notes = data.get("resolution_notes") if data else None
    return service.return_to_ai(lead_id=lead_id, operator_id=x_admin_id, resolution_notes=notes)


@router.get("/{lead_id}/clarifications")
def list_lead_clarifications(
    lead_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List clarifications for a lead."""
    from app.repositories.qualification_clarification_repo import QualificationClarificationRepository
    repo = QualificationClarificationRepository(db)
    return repo.list_for_lead(lead_id, limit=limit)


@router.post("/{lead_id}/clarifications/{clarification_id}/resolve")
def resolve_clarification(
    lead_id: uuid.UUID,
    clarification_id: uuid.UUID,
    data: Optional[dict] = None,
    x_admin_id: str = Header("operator", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Operator manually confirms or cancels a clarification."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.repositories.qualification_clarification_repo import QualificationClarificationRepository
    from app.repositories.tenant_requirement_repo import TenantRequirementRepository
    from app.models.enums import RequirementFieldStatus, RequirementSourceType
    from decimal import Decimal

    clar_repo = QualificationClarificationRepository(db)
    clar = clar_repo.get_by_id(clarification_id)
    if not clar or clar.lead_id != lead_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Clarification not found.")

    action = data.get("action", "CONFIRM") if data else "CONFIRM"
    resolved_val = data.get("resolved_value", clar.proposed_value) if data else clar.proposed_value

    if action == "CONFIRM":
        clar_repo.resolve(clar, resolved_val)
        req_repo = TenantRequirementRepository(db)
        req = req_repo.get_by_lead_id(lead_id)
        if req:
            req_repo.supersede_active_history(req.id, clar.field_name)
            req_repo.add_history(
                tenant_requirement_id=req.id,
                field_name=clar.field_name,
                value=str(resolved_val),
                status=RequirementFieldStatus.CONFIRMED,
                source_type=RequirementSourceType.MANUAL_OVERRIDE,
                confidence=Decimal("1.0000"),
            )
            # Apply to model
            if hasattr(req, clar.field_name):
                setattr(req, clar.field_name, resolved_val)
                db.commit()
    else:
        clar_repo.cancel(clar)

    return clar


# ==============================================================================
# PHASE 8: CONVERSATION MEMORY, SUMMARY & QUALIFICATION DASHBOARD
# ==============================================================================

@router.get("/{lead_id}/qualification/dashboard")
def get_qualification_dashboard(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """
    Authoritative aggregate endpoint for the Qualification Dashboard.
    Provides complete structured state, progress, clarifications, conflicts,
    latest conversation summary, recent timeline, and next expected action.
    """
    from app.services.qualification_memory_service import QualificationMemoryService
    service = QualificationMemoryService(db)
    try:
        return service.get_qualification_dashboard(lead_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/qualification/summary")
def get_qualification_summary(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Returns the latest operational conversation summary for a lead."""
    from app.services.qualification_memory_service import QualificationMemoryService
    service = QualificationMemoryService(db)
    summary = service.summary_repo.get_latest_for_lead(lead_id)
    if not summary:
        # Generate initial deterministic summary
        det_text, det_structured = service.build_deterministic_summary(lead_id)
        summary = service.summary_repo.create({
            "lead_id": lead_id,
            "summary_text": det_text,
            "structured_summary": det_structured,
        })
    from app.schemas.memory import ConversationSummaryResponse
    return ConversationSummaryResponse.model_validate(summary)


@router.post("/{lead_id}/qualification/summary/refresh")
async def refresh_qualification_summary(
    lead_id: uuid.UUID,
    x_admin_id: str = Header("operator", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Refreshes the operational conversation summary using AI and deterministic validation."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.services.qualification_memory_service import QualificationMemoryService
    from app.schemas.memory import ConversationSummaryResponse
    service = QualificationMemoryService(db)
    try:
        summary = await service.generate_or_refresh_summary(
            lead_id=lead_id,
            reason="manual_refresh",
            force=True,
            actor_id=x_admin_id,
        )
        return {
            "success": True,
            "summary": ConversationSummaryResponse.model_validate(summary),
            "refreshed_reason": "manual_refresh",
        }
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/{lead_id}/notes")
def list_lead_notes(
    lead_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Lists internal operator notes for a lead."""
    from app.repositories.conversation_note_repo import ConversationNoteRepository
    from app.schemas.memory import ConversationNoteResponse
    repo = ConversationNoteRepository(db)
    notes = repo.list_for_lead(lead_id)
    return [ConversationNoteResponse.model_validate(n) for n in notes]


@router.post("/{lead_id}/notes")
def create_lead_note(
    lead_id: uuid.UUID,
    data: dict,
    x_admin_id: str = Header("operator", alias="X-Admin-Id"),
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """Creates an internal operator note for a lead."""
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Unauthorized")
    from app.repositories.conversation_note_repo import ConversationNoteRepository
    from app.schemas.memory import ConversationNoteResponse
    note_text = data.get("note", "").strip()
    if not note_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note content cannot be empty.")
    repo = ConversationNoteRepository(db)
    note = repo.create(lead_id=lead_id, author_id=x_admin_id, note=note_text)
    return ConversationNoteResponse.model_validate(note)





