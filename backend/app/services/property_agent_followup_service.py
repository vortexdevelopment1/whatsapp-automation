import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func

from app.models.lead import Lead
from app.models.property_match import PropertyMatch
from app.models.property_listing import PropertyListing
from app.models.property_agent import PropertyAgent
from app.models.property_agent_outreach import PropertyAgentOutreach
from app.models.property_agent_followup import PropertyAgentFollowUp
from app.models.whatsapp import WhatsAppProfile
from app.models.message import WhatsAppMessage
from app.models.enums import (
    PropertyMatchStatus,
    PropertyAgentOutreachStatus,
    PropertyAgentFollowUpType,
    PropertyAgentFollowUpStatus,
    ListingAvailabilityStatus,
    MessageDirection,
)
from app.schemas.audit import AuditLogCreate
from app.repositories.audit_repo import AuditRepository
from app.services.agent_followup_config import AgentFollowUpConfig, DEFAULT_AGENT_FOLLOWUP_CONFIG
from app.services.whatsapp_service import WhatsAppService

logger = logging.getLogger(__name__)


class PropertyAgentFollowUpService:
    """
    Coordinates agent follow-up lifecycle:
    - Schedules initial follow-up when outreach is sent
    - Scans for due follow-ups (batch processing)
    - Verifies reply state, listing validity, and match state immediately before send
    - Prevents duplicates via unique idempotency keys
    - Dispatches concise follow-up nudges via WhatsAppService
    - Marks outreach UNRESPONSIVE and triggers fallback when max attempts are exhausted
    """

    def __init__(self, db: Session, wa_service: Optional[WhatsAppService] = None):
        self.db = db
        self.whatsapp_service = wa_service or WhatsAppService(db)
        self.audit_repo = AuditRepository(db)

    def _get_active_whatsapp_profile(self) -> WhatsAppProfile:
        profile = self.db.query(WhatsAppProfile).first()
        if not profile:
            from app.models.agent import Agent
            agent = self.db.query(Agent).first()
            if not agent:
                agent = Agent(
                    full_name="Platform Concierge Agent",
                    email=f"concierge_{uuid.uuid4().hex[:6]}@platform.sg",
                    phone="+6590000000",
                    agency_name="Platform Property",
                    registration_number="R000001A",
                )
                self.db.add(agent)
                self.db.commit()
                self.db.refresh(agent)

            profile = WhatsAppProfile(
                agent_id=agent.id,
                phone_number_id="pn_platform_default",
                display_phone_number="+6590000000",
                business_display_name="Platform Property Concierge",
            )
            self.db.add(profile)
            self.db.commit()
            self.db.refresh(profile)
        return profile

    def schedule_initial_followup(
        self,
        outreach_id: uuid.UUID,
        config: Optional[AgentFollowUpConfig] = None,
    ) -> PropertyAgentFollowUp:
        """
        Calculates initial SLA due time and creates the first follow-up task.
        """
        cfg = config or DEFAULT_AGENT_FOLLOWUP_CONFIG
        outreach = self.db.query(PropertyAgentOutreach).filter(PropertyAgentOutreach.id == outreach_id).first()
        if not outreach:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PropertyAgentOutreach '{outreach_id}' not found.",
            )

        now = datetime.now(timezone.utc)
        due_at = (outreach.sent_at or now) + timedelta(minutes=cfg.initial_response_sla_minutes)

        outreach.response_due_at = due_at
        outreach.followup_attempt = 0

        idempotency_key = f"property-agent-followup:{outreach.id}:1"
        existing = (
            self.db.query(PropertyAgentFollowUp)
            .filter(PropertyAgentFollowUp.idempotency_key == idempotency_key)
            .first()
        )
        if existing:
            return existing

        followup = PropertyAgentFollowUp(
            lead_id=outreach.lead_id,
            property_match_id=outreach.property_match_id,
            listing_id=outreach.listing_id,
            property_agent_id=outreach.property_agent_id,
            outreach_id=outreach.id,
            conversation_id=outreach.conversation_id,
            followup_type=PropertyAgentFollowUpType.INITIAL_RESPONSE_WAIT.value,
            attempt_number=1,
            status=PropertyAgentFollowUpStatus.PENDING.value,
            due_at=due_at,
            idempotency_key=idempotency_key,
        )
        self.db.add(followup)
        self.db.commit()
        self.db.refresh(followup)

        self._create_audit_log(
            event_type="PROPERTY_AGENT_FOLLOWUP_SCHEDULED",
            lead_id=outreach.lead_id,
            actor_id="system",
            details={
                "outreach_id": str(outreach.id),
                "followup_id": str(followup.id),
                "attempt_number": 1,
                "due_at": due_at.isoformat(),
            },
        )
        return followup

    def cancel_pending_followups_for_outreach(
        self,
        outreach_id: uuid.UUID,
        reason: str = "AGENT_ALREADY_REPLIED",
        actor_id: str = "system",
    ) -> int:
        """
        Cancels all pending or due follow-ups for a given outreach record.
        """
        pending_list = (
            self.db.query(PropertyAgentFollowUp)
            .filter(
                PropertyAgentFollowUp.outreach_id == outreach_id,
                PropertyAgentFollowUp.status.in_([
                    PropertyAgentFollowUpStatus.PENDING.value,
                    PropertyAgentFollowUpStatus.DUE.value,
                ]),
            )
            .all()
        )
        count = 0
        now = datetime.now(timezone.utc)
        for f in pending_list:
            f.status = PropertyAgentFollowUpStatus.CANCELLED.value
            f.cancelled_at = now
            f.cancellation_reason = reason
            self.db.add(f)
            count += 1

        if count > 0:
            self.db.commit()
            self._create_audit_log(
                event_type="PROPERTY_AGENT_FOLLOWUP_CANCELLED",
                lead_id=None,
                actor_id=actor_id,
                details={
                    "outreach_id": str(outreach_id),
                    "cancelled_count": count,
                    "reason": reason,
                },
            )
        return count

    def cancel_pending_followups_for_match(
        self,
        match_id: uuid.UUID,
        reason: str = "MATCH_NO_LONGER_ACTIVE",
        actor_id: str = "system",
    ) -> int:
        """
        Cancels all pending follow-ups for a property match.
        """
        pending_list = (
            self.db.query(PropertyAgentFollowUp)
            .filter(
                PropertyAgentFollowUp.property_match_id == match_id,
                PropertyAgentFollowUp.status.in_([
                    PropertyAgentFollowUpStatus.PENDING.value,
                    PropertyAgentFollowUpStatus.DUE.value,
                ]),
            )
            .all()
        )
        count = 0
        now = datetime.now(timezone.utc)
        for f in pending_list:
            f.status = PropertyAgentFollowUpStatus.CANCELLED.value
            f.cancelled_at = now
            f.cancellation_reason = reason
            self.db.add(f)
            count += 1

        if count > 0:
            self.db.commit()
            self._create_audit_log(
                event_type="PROPERTY_AGENT_FOLLOWUP_CANCELLED",
                lead_id=None,
                actor_id=actor_id,
                details={
                    "match_id": str(match_id),
                    "cancelled_count": count,
                    "reason": reason,
                },
            )
        return count

    def process_due_followups(
        self,
        config: Optional[AgentFollowUpConfig] = None,
        actor_id: str = "scheduler",
    ) -> List[Dict[str, Any]]:
        """
        Identifies and executes all due follow-ups in batch.
        Guarantees idempotency and safe pre-flight state validation.
        """
        cfg = config or DEFAULT_AGENT_FOLLOWUP_CONFIG
        now = datetime.now(timezone.utc)

        due_tasks = (
            self.db.query(PropertyAgentFollowUp)
            .filter(
                PropertyAgentFollowUp.status.in_([
                    PropertyAgentFollowUpStatus.PENDING.value,
                    PropertyAgentFollowUpStatus.DUE.value,
                ]),
                PropertyAgentFollowUp.due_at <= now,
            )
            .order_by(PropertyAgentFollowUp.due_at.asc())
            .all()
        )

        results: List[Dict[str, Any]] = []

        for task in due_tasks:
            try:
                res = self._process_single_followup(task, cfg=cfg, actor_id=actor_id)
                results.append(res)
            except Exception as e:
                logger.error(f"Error processing follow-up task {task.id}: {e}", exc_info=True)
                task.status = PropertyAgentFollowUpStatus.FAILED.value
                self.db.add(task)
                self.db.commit()
                results.append({
                    "task_id": str(task.id),
                    "status": "FAILED",
                    "error": str(e),
                })

        return results

    def _process_single_followup(
        self,
        task: PropertyAgentFollowUp,
        cfg: AgentFollowUpConfig,
        actor_id: str,
    ) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)

        # 1. Fresh state fetch
        outreach = self.db.query(PropertyAgentOutreach).filter(PropertyAgentOutreach.id == task.outreach_id).first()
        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == task.property_match_id).first()
        listing = self.db.query(PropertyListing).filter(PropertyListing.id == task.listing_id).first()
        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == task.property_agent_id).first()

        if not outreach or not match or not agent:
            task.status = PropertyAgentFollowUpStatus.CANCELLED.value
            task.cancellation_reason = "ENTITIES_NOT_FOUND"
            task.cancelled_at = now
            self.db.commit()
            return {"task_id": str(task.id), "status": "CANCELLED", "reason": "ENTITIES_NOT_FOUND"}

        # 2. Check if agent already replied!
        if outreach.status == PropertyAgentOutreachStatus.REPLIED:
            task.status = PropertyAgentFollowUpStatus.CANCELLED.value
            task.cancellation_reason = "AGENT_ALREADY_REPLIED"
            task.cancelled_at = now
            self.db.commit()
            return {"task_id": str(task.id), "status": "CANCELLED", "reason": "AGENT_ALREADY_REPLIED"}

        # Check if an inbound message from this agent was received
        cutoff_time = (outreach.sent_at or outreach.created_at) - timedelta(seconds=10)
        recent_reply = (
            self.db.query(WhatsAppMessage)
            .filter(
                WhatsAppMessage.sender == agent.phone_normalized,
                WhatsAppMessage.direction.in_([MessageDirection.INBOUND, "INBOUND"]),
                WhatsAppMessage.created_at >= cutoff_time,
            )
            .first()
        )
        if recent_reply:
            task.status = PropertyAgentFollowUpStatus.CANCELLED.value
            task.cancellation_reason = "AGENT_INBOUND_MESSAGE_DETECTED"
            task.cancelled_at = now
            outreach.status = PropertyAgentOutreachStatus.REPLIED
            outreach.replied_at = recent_reply.created_at
            self.db.commit()
            return {"task_id": str(task.id), "status": "CANCELLED", "reason": "AGENT_INBOUND_MESSAGE_DETECTED"}

        # 3. Check if listing became unavailable or inactive
        if listing and (
            listing.listing_status != "ACTIVE" or
            listing.availability_status == ListingAvailabilityStatus.UNAVAILABLE.value
        ):
            task.status = PropertyAgentFollowUpStatus.CANCELLED.value
            task.cancellation_reason = "LISTING_UNAVAILABLE_OR_INACTIVE"
            task.cancelled_at = now
            self.db.commit()
            from app.services.property_verification_fallback_service import PropertyVerificationFallbackService
            fallback_svc = PropertyVerificationFallbackService(self.db)
            fallback_res = fallback_svc.execute_fallback(match.id, config=cfg, actor_id=actor_id)
            return {
                "task_id": str(task.id),
                "status": "CANCELLED",
                "reason": "LISTING_UNAVAILABLE",
                "fallback": fallback_res.model_dump(),
            }

        # 4. Check if match already verified / conditional / unavailable
        if match.match_status in [
            PropertyMatchStatus.AVAILABLE.value,
            PropertyMatchStatus.UNAVAILABLE.value,
            PropertyMatchStatus.CONDITIONAL.value,
            PropertyMatchStatus.VERIFIED_CANDIDATE.value,
        ]:
            task.status = PropertyAgentFollowUpStatus.CANCELLED.value
            task.cancellation_reason = f"MATCH_ALREADY_{match.match_status}"
            task.cancelled_at = now
            self.db.commit()
            return {"task_id": str(task.id), "status": "CANCELLED", "reason": f"MATCH_ALREADY_{match.match_status}"}

        # 5. Check if max follow-up attempts exhausted or fallback review task due
        if task.attempt_number > cfg.max_followup_attempts or task.followup_type == PropertyAgentFollowUpType.FALLBACK_REVIEW.value:
            # Mark outreach UNRESPONSIVE
            outreach.status = PropertyAgentOutreachStatus.UNRESPONSIVE
            match.match_status = PropertyMatchStatus.AGENT_UNRESPONSIVE.value
            match.agent_verification_status = "UNRESPONSIVE"

            task.status = PropertyAgentFollowUpStatus.COMPLETED.value
            task.completed_at = now
            self.db.commit()

            self._create_audit_log(
                event_type="PROPERTY_AGENT_MARKED_UNRESPONSIVE",
                lead_id=outreach.lead_id,
                actor_id=actor_id,
                details={
                    "outreach_id": str(outreach.id),
                    "match_id": str(match.id),
                    "attempts_made": outreach.followup_attempt,
                },
            )

            # Trigger Fallback workflow
            from app.services.property_verification_fallback_service import PropertyVerificationFallbackService
            fallback_svc = PropertyVerificationFallbackService(self.db)
            fallback_res = fallback_svc.execute_fallback(match.id, config=cfg, actor_id=actor_id)

            return {
                "task_id": str(task.id),
                "status": "UNRESPONSIVE_FALLBACK_TRIGGERED",
                "fallback": fallback_res.model_dump(),
            }

        # 6. Build concise follow-up message content
        ref_code = outreach.reference_code or f"PM-{str(match.id)[:8].upper()}"
        if task.attempt_number == 1:
            msg_content = f"Hi, just following up regarding listing {ref_code}. Could you please confirm whether the unit is still available?"
        else:
            msg_content = f"Following up once more on listing {ref_code}. Please let us know if it is still available when convenient."

        # 7. Dispatch message via WhatsAppService
        profile = self._get_active_whatsapp_profile()
        recipient_phone = outreach.recipient_phone or agent.phone_normalized

        wa_idempotency_key = f"wa:{task.idempotency_key}"
        try:
            wa_msg = self.whatsapp_service.send_message(
                profile_id=profile.id,
                recipient=recipient_phone,
                content=msg_content,
                idempotency_key=wa_idempotency_key,
                actor_id=actor_id,
            )
        except Exception as e:
            logger.error(f"Failed to send WhatsApp follow-up for task {task.id}: {e}")
            task.status = PropertyAgentFollowUpStatus.FAILED.value
            self.db.commit()
            self._create_audit_log(
                event_type="PROPERTY_AGENT_FOLLOWUP_FAILED",
                lead_id=outreach.lead_id,
                actor_id=actor_id,
                details={"task_id": str(task.id), "error": str(e)},
            )
            return {"task_id": str(task.id), "status": "FAILED", "error": str(e)}

        # Update current follow-up task
        task.status = PropertyAgentFollowUpStatus.SENT.value
        task.sent_at = now
        task.completed_at = now
        task.message_content = msg_content
        task.whatsapp_message_id = wa_msg.id

        # Update outreach record
        outreach.followup_attempt = task.attempt_number
        self.db.add(task)
        self.db.add(outreach)
        self.db.commit()

        self._create_audit_log(
            event_type="PROPERTY_AGENT_FOLLOWUP_SENT",
            lead_id=outreach.lead_id,
            actor_id=actor_id,
            details={
                "task_id": str(task.id),
                "outreach_id": str(outreach.id),
                "attempt_number": task.attempt_number,
                "recipient": recipient_phone,
                "message_content": msg_content,
            },
        )

        # 8. Schedule NEXT follow-up or final fallback review
        next_attempt = task.attempt_number + 1
        next_due = now + timedelta(minutes=cfg.followup_delay_minutes)

        if next_attempt <= cfg.max_followup_attempts:
            next_type = (
                PropertyAgentFollowUpType.FINAL_NUDGE.value
                if next_attempt == cfg.max_followup_attempts
                else PropertyAgentFollowUpType.NUDGE.value
            )
            next_key = f"property-agent-followup:{outreach.id}:{next_attempt}"
        else:
            next_type = PropertyAgentFollowUpType.FALLBACK_REVIEW.value
            next_key = f"property-agent-followup:{outreach.id}:fallback_review"

        next_task = PropertyAgentFollowUp(
            lead_id=outreach.lead_id,
            property_match_id=outreach.property_match_id,
            listing_id=outreach.listing_id,
            property_agent_id=outreach.property_agent_id,
            outreach_id=outreach.id,
            conversation_id=outreach.conversation_id,
            followup_type=next_type,
            attempt_number=next_attempt,
            status=PropertyAgentFollowUpStatus.PENDING.value,
            due_at=next_due,
            idempotency_key=next_key,
        )
        self.db.add(next_task)
        self.db.commit()

        return {
            "task_id": str(task.id),
            "status": "SENT",
            "attempt_number": task.attempt_number,
            "next_task_id": str(next_task.id),
            "next_due_at": next_due.isoformat(),
        }

    def send_manual_followup(
        self,
        outreach_id: uuid.UUID,
        reason: Optional[str] = None,
        actor_id: str = "operator",
        config: Optional[AgentFollowUpConfig] = None,
    ) -> PropertyAgentFollowUp:
        """
        Sends an immediate manual follow-up if within configured limits.
        """
        cfg = config or DEFAULT_AGENT_FOLLOWUP_CONFIG
        outreach = self.db.query(PropertyAgentOutreach).filter(PropertyAgentOutreach.id == outreach_id).first()
        if not outreach:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PropertyAgentOutreach '{outreach_id}' not found.",
            )

        if outreach.status == PropertyAgentOutreachStatus.REPLIED:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Agent has already replied. Manual follow-up is blocked.",
            )

        if outreach.followup_attempt >= cfg.max_followup_attempts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Maximum follow-up attempts ({cfg.max_followup_attempts}) reached.",
            )

        match = self.db.query(PropertyMatch).filter(PropertyMatch.id == outreach.property_match_id).first()
        agent = self.db.query(PropertyAgent).filter(PropertyAgent.id == outreach.property_agent_id).first()
        if not match or not agent:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Associated match or agent not found.")

        # Cancel pending automated follow-up
        self.cancel_pending_followups_for_outreach(outreach_id, reason="SUPERSEDED_BY_MANUAL_FOLLOWUP", actor_id=actor_id)

        now = datetime.now(timezone.utc)
        attempt_number = outreach.followup_attempt + 1
        ref_code = outreach.reference_code or f"PM-{str(match.id)[:8].upper()}"

        if attempt_number == 1:
            msg_content = f"Hi, just following up regarding listing {ref_code}. Could you please confirm whether the unit is still available?"
        else:
            msg_content = f"Following up once more on listing {ref_code}. Please let us know if it is still available when convenient."

        profile = self._get_active_whatsapp_profile()
        recipient_phone = outreach.recipient_phone or agent.phone_normalized
        idempotency_key = f"property-agent-manual-followup:{outreach.id}:{attempt_number}:{int(now.timestamp())}"

        wa_msg = self.whatsapp_service.send_message(
            profile_id=profile.id,
            recipient=recipient_phone,
            content=msg_content,
            idempotency_key=f"wa:{idempotency_key}",
            actor_id=actor_id,
        )

        followup = PropertyAgentFollowUp(
            lead_id=outreach.lead_id,
            property_match_id=outreach.property_match_id,
            listing_id=outreach.listing_id,
            property_agent_id=outreach.property_agent_id,
            outreach_id=outreach.id,
            conversation_id=outreach.conversation_id,
            followup_type=PropertyAgentFollowUpType.NUDGE.value,
            attempt_number=attempt_number,
            status=PropertyAgentFollowUpStatus.SENT.value,
            due_at=now,
            sent_at=now,
            completed_at=now,
            message_content=msg_content,
            whatsapp_message_id=wa_msg.id,
            idempotency_key=idempotency_key,
        )
        outreach.followup_attempt = attempt_number
        self.db.add(followup)
        self.db.add(outreach)
        self.db.commit()
        self.db.refresh(followup)

        self._create_audit_log(
            event_type="PROPERTY_AGENT_MANUAL_FOLLOWUP_SENT",
            lead_id=outreach.lead_id,
            actor_id=actor_id,
            details={
                "outreach_id": str(outreach.id),
                "followup_id": str(followup.id),
                "attempt_number": attempt_number,
                "reason": reason,
            },
        )

        # Schedule next task if within limits
        next_attempt = attempt_number + 1
        next_due = now + timedelta(minutes=cfg.followup_delay_minutes)
        if next_attempt <= cfg.max_followup_attempts:
            next_type = (
                PropertyAgentFollowUpType.FINAL_NUDGE.value
                if next_attempt == cfg.max_followup_attempts
                else PropertyAgentFollowUpType.NUDGE.value
            )
            next_key = f"property-agent-followup:{outreach.id}:{next_attempt}"
        else:
            next_type = PropertyAgentFollowUpType.FALLBACK_REVIEW.value
            next_key = f"property-agent-followup:{outreach.id}:fallback_review"

        next_task = PropertyAgentFollowUp(
            lead_id=outreach.lead_id,
            property_match_id=outreach.property_match_id,
            listing_id=outreach.listing_id,
            property_agent_id=outreach.property_agent_id,
            outreach_id=outreach.id,
            conversation_id=outreach.conversation_id,
            followup_type=next_type,
            attempt_number=next_attempt,
            status=PropertyAgentFollowUpStatus.PENDING.value,
            due_at=next_due,
            idempotency_key=next_key,
        )
        self.db.add(next_task)
        self.db.commit()

        return followup

    def cancel_followup(
        self,
        followup_id: uuid.UUID,
        reason: str = "Operator cancelled",
        actor_id: str = "operator",
    ) -> PropertyAgentFollowUp:
        """
        Manually cancels a specific follow-up task.
        """
        followup = self.db.query(PropertyAgentFollowUp).filter(PropertyAgentFollowUp.id == followup_id).first()
        if not followup:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"PropertyAgentFollowUp '{followup_id}' not found.",
            )

        if followup.status in [
            PropertyAgentFollowUpStatus.SENT.value,
            PropertyAgentFollowUpStatus.COMPLETED.value,
        ]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel follow-up that is already in '{followup.status}' state.",
            )

        now = datetime.now(timezone.utc)
        followup.status = PropertyAgentFollowUpStatus.CANCELLED.value
        followup.cancelled_at = now
        followup.cancellation_reason = reason
        self.db.commit()
        self.db.refresh(followup)

        self._create_audit_log(
            event_type="PROPERTY_AGENT_FOLLOWUP_CANCELLED",
            lead_id=followup.lead_id,
            actor_id=actor_id,
            details={
                "followup_id": str(followup.id),
                "reason": reason,
            },
        )
        return followup

    def _create_audit_log(
        self,
        event_type: str,
        lead_id: Optional[uuid.UUID],
        actor_id: str,
        details: Dict[str, Any],
    ) -> None:
        try:
            self.audit_repo.log(
                AuditLogCreate(
                    actor_id=actor_id,
                    action=event_type,
                    entity_type="property_agent_followup",
                    entity_id=str(details.get("followup_id") or details.get("outreach_id") or lead_id or uuid.uuid4()),
                    new_value=details,
                )
            )
        except Exception as e:
            logger.warning(f"Failed to record audit log for {event_type}: {e}")
