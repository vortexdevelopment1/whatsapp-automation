import hmac
import hashlib
import json
import uuid
from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Header, Request, Response, BackgroundTasks, status, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.sql import func


from app.api.deps import get_db
from app.core.config import settings
from app.core.database import SessionLocal
from app.models.enums import MessageDirection, MessageType, WebhookProcessingStatus, LeadStatus, ConsentStatus, OptOutStatus, ContactEligibility
from app.models.message import WhatsAppMessage
from app.models.webhook_event import WebhookEvent
from app.models.whatsapp import WhatsAppProfile
from app.models.lead import Lead
from app.repositories.message_repo import MessageRepository
from app.repositories.lead_repo import LeadRepository
from app.services.qualification_conversation_processor import QualificationConversationProcessor

router = APIRouter(prefix="/webhook/whatsapp", tags=["webhook"])


def verify_meta_signature(payload_bytes: bytes, signature_header: Optional[str]) -> bool:
    """Validate sha256 HMAC signature from Meta if META_APP_SECRET is configured."""
    if not settings.META_APP_SECRET or not signature_header:
        return True  # If no secret configured in dev/test, skip validation

    if not signature_header.startswith("sha256="):
        return False

    expected_hash = signature_header[7:]
    mac = hmac.new(settings.META_APP_SECRET.encode("utf-8"), msg=payload_bytes, digestmod=hashlib.sha256)
    return hmac.compare_digest(mac.hexdigest(), expected_hash)


async def run_qualification_worker(message_id: uuid.UUID):
    """Background task executing the live qualification loop."""
    db = SessionLocal()
    try:
        processor = QualificationConversationProcessor(db)
        await processor.process_message(message_id)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).error(f"Background qualification processing failed for message {message_id}: {exc}")
    finally:
        db.close()


@router.get("")
def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """Meta webhook verification endpoint."""
    if hub_mode == "subscribe" and hub_verify_token == settings.META_VERIFY_TOKEN:
        return Response(content=str(hub_challenge or ""), media_type="text/plain", status_code=status.HTTP_200_OK)
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")


@router.post("")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    async_processing: bool = Query(True, description="Whether to run processor in background task"),
    db: Session = Depends(get_db),
):
    """
    Ingests inbound Meta WhatsApp webhooks quickly, deduplicates, stores message,
    and dispatches qualification processing.
    """
    body_bytes = await request.body()

    if not verify_meta_signature(body_bytes, x_hub_signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Meta webhook signature")

    try:
        payload = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
    except Exception:
        payload = {}

    msg_repo = MessageRepository(db)
    lead_repo = LeadRepository(db)

    # Check for delivery status updates (Meta statuses or test status callback)
    statuses_list = []
    if "entry" in payload and isinstance(payload["entry"], list) and len(payload["entry"]) > 0:
        changes = payload["entry"][0].get("changes", [])
        if changes and isinstance(changes, list):
            value = changes[0].get("value", {})
            if "statuses" in value and isinstance(value["statuses"], list):
                statuses_list = value["statuses"]
    elif "status" in payload and ("provider_message_id" in payload or "id" in payload) and not payload.get("messages") and not payload.get("content"):
        statuses_list = [{
            "id": payload.get("provider_message_id") or payload.get("id"),
            "status": payload.get("status"),
            "errors": payload.get("errors"),
        }]

    if statuses_list:
        from app.models.property_agent_outreach import PropertyAgentOutreach
        from app.models.lead_outreach import LeadOutreach
        from app.models.enums import PropertyAgentOutreachStatus, OutreachStatus

        updated_count = 0
        for s in statuses_list:
            p_msg_id = s.get("id")
            s_val = str(s.get("status", "")).lower()
            if not p_msg_id:
                continue

            msg = msg_repo.get_by_provider_message_id(p_msg_id)
            if msg:
                msg.provider_status = s_val
                db.add(msg)

            agent_outreach = (
                db.query(PropertyAgentOutreach)
                .filter(PropertyAgentOutreach.provider_message_id == p_msg_id)
                .first()
            )
            if agent_outreach:
                if s_val == "delivered" and not agent_outreach.delivered_at:
                    agent_outreach.delivered_at = func.now()
                elif s_val == "read" and not agent_outreach.read_at:
                    agent_outreach.read_at = func.now()
                elif s_val == "sent" and not agent_outreach.sent_at:
                    agent_outreach.sent_at = func.now()

                # Do not let late delivery callbacks overwrite REPLIED state
                if agent_outreach.status != PropertyAgentOutreachStatus.REPLIED:
                    if s_val == "sent":
                        agent_outreach.status = PropertyAgentOutreachStatus.SENT
                    elif s_val == "delivered":
                        agent_outreach.status = PropertyAgentOutreachStatus.DELIVERED
                    elif s_val == "read":
                        agent_outreach.status = PropertyAgentOutreachStatus.READ
                    elif s_val == "failed":
                        agent_outreach.status = PropertyAgentOutreachStatus.FAILED
                        agent_outreach.error_message = str(s.get("errors") or "Delivery failed")
                db.add(agent_outreach)
                updated_count += 1

            if msg:
                lead_outreach = db.query(LeadOutreach).filter(LeadOutreach.whatsapp_message_id == msg.id).first()
                if lead_outreach:
                    if s_val == "delivered":
                        lead_outreach.status = OutreachStatus.DELIVERED
                        lead_outreach.delivered_at = func.now()
                    elif s_val == "read":
                        lead_outreach.status = OutreachStatus.READ
                        lead_outreach.read_at = func.now()
                    elif s_val == "failed":
                        lead_outreach.status = OutreachStatus.FAILED
                        lead_outreach.error_message = str(s.get("errors") or "Delivery failed")
                    db.add(lead_outreach)

        db.commit()
        return {"status": "statuses_processed", "count": len(statuses_list), "updated": updated_count}

    # 1. Parse message details (supports Meta payload and simplified test payload)
    provider_msg_id = None
    sender = None
    recipient = None
    content = ""
    phone_number_id = None

    if "entry" in payload and isinstance(payload["entry"], list) and len(payload["entry"]) > 0:
        changes = payload["entry"][0].get("changes", [])
        if changes and isinstance(changes, list):
            value = changes[0].get("value", {})
            phone_number_id = value.get("metadata", {}).get("phone_number_id")
            messages = value.get("messages", [])
            if messages:
                m = messages[0]
                provider_msg_id = m.get("id")
                sender = m.get("from")
                if "text" in m and "body" in m["text"]:
                    content = m["text"]["body"]
                elif "button" in m and "text" in m["button"]:
                    content = m["button"]["text"]
    else:
        # Simplified direct test payload
        provider_msg_id = payload.get("provider_message_id") or payload.get("id")
        sender = payload.get("sender") or payload.get("from")
        recipient = payload.get("recipient") or payload.get("to")
        content = payload.get("content") or payload.get("text") or ""
        phone_number_id = payload.get("phone_number_id")

    if not provider_msg_id:
        provider_msg_id = f"wamid.in_{uuid.uuid4().hex[:16]}"

    # Deduplication check
    existing_msg = msg_repo.get_by_provider_message_id(provider_msg_id)
    if existing_msg:
        return {"status": "duplicate_ignored", "message_id": str(existing_msg.id)}

    # Store raw webhook event
    event = WebhookEvent(
        provider="meta",
        provider_event_id=provider_msg_id,
        event_type="messages",
        payload=payload,
        processing_status=WebhookProcessingStatus.PROCESSED,
    )
    db.add(event)
    db.commit()

    # Resolve WhatsApp profile
    profile = None
    if phone_number_id:
        profile = db.query(WhatsAppProfile).filter(WhatsAppProfile.phone_number_id == phone_number_id).first()
    if not profile:
        profile = db.query(WhatsAppProfile).first()

    if not profile:
        # Create fallback profile
        profile = WhatsAppProfile(phone_number_id=phone_number_id or "pn_default", display_phone_number="+6590000000")
        db.add(profile)
        db.commit()
        db.refresh(profile)

    # Normalize phone
    sender_clean = sender or "+6598765432"
    if not sender_clean.startswith("+"):
        sender_clean = f"+{sender_clean}"

    # Check if sender is a registered PropertyAgent
    from app.models.property_agent import PropertyAgent
    from app.models.property_agent_outreach import PropertyAgentOutreach
    from app.models.enums import PropertyAgentOutreachStatus
    from sqlalchemy import or_

    registered_agent = (
        db.query(PropertyAgent)
        .filter(or_(PropertyAgent.phone_normalized == sender_clean, PropertyAgent.phone == sender_clean))
        .first()
    )

    if registered_agent:
        # Store inbound property-agent message
        new_msg = WhatsAppMessage(
            whatsapp_profile_id=profile.id,
            provider_message_id=provider_msg_id,
            direction=MessageDirection.INBOUND,
            message_type=MessageType.TEXT,
            sender=sender_clean,
            recipient=recipient or profile.display_phone_number or "+6590000000",
            content=content,
            provider_status="delivered",
            raw_payload=payload,
        )
        db.add(new_msg)
        db.commit()
        db.refresh(new_msg)

        # Inbound correlation foundation for PropertyAgent:
        pending_outreaches = (
            db.query(PropertyAgentOutreach)
            .filter(
                PropertyAgentOutreach.property_agent_id == registered_agent.id,
                PropertyAgentOutreach.status.in_([
                    PropertyAgentOutreachStatus.QUEUED,
                    PropertyAgentOutreachStatus.SENT,
                    PropertyAgentOutreachStatus.DELIVERED,
                    PropertyAgentOutreachStatus.READ,
                ]),
            )
            .order_by(PropertyAgentOutreach.created_at.desc())
            .all()
        )

        matched_outreach = None
        correlation_status = "NONE"

        if len(pending_outreaches) == 1:
            matched_outreach = pending_outreaches[0]
            correlation_status = "EXACT_SINGLE_PENDING"
        elif len(pending_outreaches) > 1:
            # Look for reference code in content
            for o in pending_outreaches:
                if o.reference_code and o.reference_code.upper() in content.upper():
                    matched_outreach = o
                    correlation_status = "MATCHED_BY_REFERENCE_CODE"
                    break
            if not matched_outreach:
                correlation_status = "AMBIGUOUS_NEEDS_REVIEW"

        verification_result = None
        if matched_outreach:
            matched_outreach.status = PropertyAgentOutreachStatus.REPLIED
            matched_outreach.replied_at = func.now()
            if matched_outreach.conversation:
                matched_outreach.conversation.last_message_at = func.now()
            db.commit()

            # Module 4 Phase 6: Run response understanding and availability verification
            try:
                from app.services.property_agent_response_understanding_service import PropertyAgentResponseUnderstandingService
                from app.services.property_availability_verification_service import PropertyAvailabilityVerificationService
                understanding_service = PropertyAgentResponseUnderstandingService(db)
                verification_service = PropertyAvailabilityVerificationService(db)
                analysis = await understanding_service.analyze_response(
                    message_id=new_msg.id,
                    override_match_id=matched_outreach.property_match_id,
                    actor_id="agent_webhook",
                )
                verification_result = verification_service.apply_verification_from_extraction(analysis, actor_id="agent_webhook")
            except Exception as e:
                logger.error(f"Error executing agent response verification in webhook: {e}")
        elif correlation_status == "AMBIGUOUS_NEEDS_REVIEW":
            for o in pending_outreaches:
                o.error_message = "Ambiguous reply received: multiple active matches exist and no reference code was provided."
                if o.property_match:
                    o.property_match.agent_verification_status = "AMBIGUOUS_NEEDS_REVIEW"
                    o.property_match.availability_status = "NEEDS_REVIEW"
            db.commit()

        # Check if there are active viewing availability requests for this agent
        from app.models.viewing_availability_request import ViewingAvailabilityRequest
        from app.models.enums import ViewingAvailabilityRequestStatus, ViewingStatus
        from app.models.viewing import Viewing
        pending_viewing_requests = (
            db.query(ViewingAvailabilityRequest)
            .filter(
                ViewingAvailabilityRequest.property_agent_id == registered_agent.id,
                ViewingAvailabilityRequest.status.in_([
                    ViewingAvailabilityRequestStatus.PENDING,
                    ViewingAvailabilityRequestStatus.QUEUED,
                    ViewingAvailabilityRequestStatus.SENT,
                    ViewingAvailabilityRequestStatus.DELIVERED,
                    ViewingAvailabilityRequestStatus.READ,
                ]),
            )
            .all()
        )

        viewing_result = None
        if pending_viewing_requests:
            try:
                from app.services.viewing_availability_understanding_service import ViewingAvailabilityUnderstandingService
                viewing_service = ViewingAvailabilityUnderstandingService(db)
                viewing_result = await viewing_service.process_inbound_agent_message(
                    message_id=new_msg.id,
                    actor_id="agent_webhook",
                )
            except Exception as e:
                logger.error(f"Error executing viewing availability processing in webhook: {e}")

        # Check if there are active viewing confirmations pending for this agent
        pending_confirmation_viewings = (
            db.query(Viewing)
            .filter(
                Viewing.property_agent_id == registered_agent.id,
                Viewing.status.in_([
                    ViewingStatus.AWAITING_AGENT_CONFIRMATION,
                    ViewingStatus.SLOT_PROPOSED,
                ]),
            )
            .all()
        )

        agent_confirmation_result = None
        if pending_confirmation_viewings:
            try:
                from app.services.viewing_confirmation_service import ViewingConfirmationService
                conf_service = ViewingConfirmationService(db)
                agent_confirmation_result = await conf_service.process_inbound_agent_confirmation(
                    message_id=new_msg.id,
                    agent_id=registered_agent.id,
                    actor_id="agent_webhook",
                )
            except Exception as e:
                logger.error(f"Error executing agent confirmation processing in webhook: {e}")

        # Check if there are confirmed/active viewings for this agent (Module 5 Phase 6)
        agent_operation_result = None
        confirmed_agent_viewings = (
            db.query(Viewing)
            .filter(
                Viewing.property_agent_id == registered_agent.id,
                Viewing.status.in_([
                    ViewingStatus.CONFIRMED,
                    ViewingStatus.RESCHEDULE_REQUESTED,
                ]),
            )
            .all()
        )
        if confirmed_agent_viewings and not pending_confirmation_viewings and not pending_viewing_requests:
            try:
                from app.services.viewing_operation_understanding_service import ViewingOperationUnderstandingService
                op_service = ViewingOperationUnderstandingService(db)
                agent_operation_result = await op_service.process_inbound_agent_operation(
                    message_id=new_msg.id,
                    agent_id=registered_agent.id,
                    actor_id="agent_webhook",
                )
            except Exception as e:
                logger.error(f"Error executing agent viewing operation in webhook: {e}")

        return {
            "status": "property_agent_reply_received",
            "message_id": str(new_msg.id),
            "property_agent_id": str(registered_agent.id),
            "correlation_status": correlation_status,
            "matched_outreach_id": str(matched_outreach.id) if matched_outreach else None,
            "verification_status": verification_result.get("status") if verification_result else None,
            "match_status": verification_result.get("match_status") if verification_result else None,
            "viewing_availability_status": viewing_result.get("result", {}).get("status") if viewing_result else None,
            "confirmation_status": agent_confirmation_result.intent.value if agent_confirmation_result else None,
            "operation_intent": agent_operation_result.get("intent") if agent_operation_result else None,
            "provider_message_id": provider_msg_id,
        }


    # Otherwise, sender is a Tenant Lead
    lead = lead_repo.get_by_phone_normalized(sender_clean)
    if not lead:
        lead = Lead(
            phone=sender_clean,
            phone_normalized=sender_clean,
            status=LeadStatus.REPLIED,
            consent_status=ConsentStatus.CONSENTED,
            opt_out_status=OptOutStatus.ACTIVE,
            contact_eligibility=ContactEligibility.ELIGIBLE,
            assigned_whatsapp_profile_id=profile.id,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)

    # Store inbound message
    new_msg = WhatsAppMessage(
        whatsapp_profile_id=profile.id,
        provider_message_id=provider_msg_id,
        direction=MessageDirection.INBOUND,
        message_type=MessageType.TEXT,
        sender=sender_clean,
        recipient=recipient or profile.display_phone_number or "+6590000000",
        content=content,
        provider_status="delivered",
        raw_payload=payload,
    )
    db.add(new_msg)
    db.commit()
    db.refresh(new_msg)

    # Check if lead has active viewings in SLOTS_AVAILABLE or AWAITING_TENANT_AVAILABILITY
    from app.models.viewing import Viewing
    from app.models.enums import ViewingStatus
    active_scheduling_viewing = (
        db.query(Viewing)
        .filter(
            Viewing.lead_id == lead.id,
            Viewing.status.in_([
                ViewingStatus.SLOTS_AVAILABLE,
                ViewingStatus.AWAITING_TENANT_AVAILABILITY,
            ]),
        )
        .first()
    )

    scheduling_result = None
    is_takeover = getattr(lead, "human_takeover", False) or (lead.tenant_requirement and getattr(lead.tenant_requirement, "ai_paused", False))
    if active_scheduling_viewing and not is_takeover:
        try:
            from app.services.tenant_viewing_availability_understanding_service import TenantViewingAvailabilityUnderstandingService
            tenant_understanding_service = TenantViewingAvailabilityUnderstandingService(db)
            scheduling_result = await tenant_understanding_service.process_inbound_tenant_message(
                message_id=new_msg.id,
                lead_id=lead.id,
                actor_id="tenant",
            )
        except Exception as e:
            logger.error(f"Error executing tenant viewing availability understanding in webhook: {e}")

    # Check if lead has active viewing confirmations pending
    active_confirmation_viewing = (
        db.query(Viewing)
        .filter(
            Viewing.lead_id == lead.id,
            Viewing.status.in_([
                ViewingStatus.AWAITING_TENANT_CONFIRMATION,
                ViewingStatus.SLOT_PROPOSED,
            ]),
        )
        .first()
    )

    confirmation_result = None
    if active_confirmation_viewing and not is_takeover:
        try:
            from app.services.viewing_confirmation_service import ViewingConfirmationService
            tenant_conf_service = ViewingConfirmationService(db)
            confirmation_result = await tenant_conf_service.process_inbound_tenant_confirmation(
                message_id=new_msg.id,
                lead_id=lead.id,
                actor_id="tenant",
            )
        except Exception as e:
            logger.error(f"Error executing tenant viewing confirmation in webhook: {e}")

    # Check if lead has confirmed/active viewings (Module 5 Phase 6: reminders replies, reschedule, cancel)
    active_confirmed_viewing = (
        db.query(Viewing)
        .filter(
            Viewing.lead_id == lead.id,
            Viewing.status.in_([
                ViewingStatus.CONFIRMED,
                ViewingStatus.RESCHEDULE_REQUESTED,
            ]),
        )
        .first()
    )

    operation_result = None
    if active_confirmed_viewing and not active_scheduling_viewing and not active_confirmation_viewing and not is_takeover:
        try:
            from app.services.viewing_operation_understanding_service import ViewingOperationUnderstandingService
            op_service = ViewingOperationUnderstandingService(db)
            operation_result = await op_service.process_inbound_tenant_operation(
                message_id=new_msg.id,
                lead_id=lead.id,
                actor_id="tenant",
            )
        except Exception as e:
            logger.error(f"Error executing tenant viewing operation in webhook: {e}")

    # Dispatch qualification processing if not handling scheduling, confirmation, or viewing operation
    has_handled_viewing_op = bool(operation_result and operation_result.get("action") in ["RESCHEDULE_INITIATED", "VIEWING_CANCELLED", "VIEWING_CONFIRMED_ACK"])
    if not active_scheduling_viewing and not active_confirmation_viewing and not has_handled_viewing_op:
        if async_processing:
            background_tasks.add_task(run_qualification_worker, new_msg.id)
        else:
            # Synchronous execution (useful for immediate testing)
            processor = QualificationConversationProcessor(db)
            await processor.process_message(new_msg.id, lead.id)

    return {
        "status": "received",
        "message_id": str(new_msg.id),
        "lead_id": str(lead.id),
        "scheduling_status": scheduling_result.intent.value if scheduling_result else None,
        "proposed_slot_id": str(scheduling_result.selected_slot_id) if (scheduling_result and scheduling_result.selected_slot_id) else None,
        "confirmation_status": confirmation_result.intent.value if confirmation_result else None,
        "operation_intent": operation_result.get("intent") if operation_result else None,
        "provider_message_id": provider_msg_id,
    }

