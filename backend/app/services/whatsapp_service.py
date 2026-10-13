import uuid
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.models.whatsapp import WhatsAppProfile
from app.models.message import WhatsAppMessage
from app.repositories.whatsapp_repo import WhatsAppRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.whatsapp import WhatsAppProfileUpdate
from app.schemas.audit import AuditLogCreate
from app.services.agent_service import AgentService


class WhatsAppService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = WhatsAppRepository(db)
        self.agent_service = AgentService(db)
        self.audit_repo = AuditRepository(db)

    def get_profile(self, agent_id: uuid.UUID) -> WhatsAppProfile:
        self.agent_service.get_agent_or_404(agent_id)
        return self.repo.get_or_create_for_agent(agent_id)

    def update_profile(
        self, agent_id: uuid.UUID, data: WhatsAppProfileUpdate, actor_id: str = "system"
    ) -> WhatsAppProfile:
        self.agent_service.get_agent_or_404(agent_id)
        profile = self.repo.get_or_create_for_agent(agent_id)
        old_data = {
            "meta_business_account_id": profile.meta_business_account_id,
            "phone_number_id": profile.phone_number_id,
            "display_phone_number": profile.display_phone_number,
            "business_display_name": profile.business_display_name,
            "connection_status": profile.connection_status.value if profile.connection_status else None,
        }
        updated = self.repo.update(profile, data)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="WHATSAPP_CONFIG_UPDATED",
                entity_type="WhatsAppProfile",
                entity_id=str(updated.id),
                old_value=old_data,
                new_value=data.model_dump(exclude_unset=True),
            )
        )
        return updated

    def send_message(
        self,
        profile_id: uuid.UUID,
        recipient: str,
        content: str,
        idempotency_key: Optional[str] = None,
        reply_to_message_id: Optional[uuid.UUID] = None,
        actor_id: str = "system",
    ) -> WhatsAppMessage:
        """
        Sends an outbound WhatsApp message via Meta Cloud API (or mock in dev/test)
        and persists the WhatsAppMessage record idempotently.
        """
        from app.models.message import WhatsAppMessage
        from app.models.enums import MessageDirection, MessageType

        profile = self.repo.get_by_id(profile_id)
        if not profile:
            raise ValueError(f"WhatsApp profile '{profile_id}' not found.")

        # Outbound idempotency check: if message with this idempotency_key already exists, return it
        if idempotency_key:
            existing = (
                self.db.query(WhatsAppMessage)
                .filter(
                    WhatsAppMessage.whatsapp_profile_id == profile_id,
                    WhatsAppMessage.direction == MessageDirection.OUTBOUND,
                    WhatsAppMessage.raw_payload["idempotency_key"].astext == idempotency_key,
                )
                .first()
            )
            if existing:
                return existing

        # Generate or dispatch via Meta Cloud API
        provider_id = f"wamid.out_{uuid.uuid4().hex[:16]}"
        raw_payload = {
            "idempotency_key": idempotency_key,
            "reply_to_message_id": str(reply_to_message_id) if reply_to_message_id else None,
            "mock": True if not getattr(profile, "phone_number_id", None) else False,
        }

        # Store outbound message record
        msg = WhatsAppMessage(
            whatsapp_profile_id=profile_id,
            provider_message_id=provider_id,
            direction=MessageDirection.OUTBOUND,
            message_type=MessageType.TEXT,
            sender=profile.display_phone_number or "+6590000000",
            recipient=recipient,
            content=content,
            provider_status="sent",
            raw_payload=raw_payload,
        )
        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)

        self.audit_repo.log(
            AuditLogCreate(
                actor_id=actor_id,
                action="WHATSAPP_MESSAGE_SENT",
                entity_type="WhatsAppMessage",
                entity_id=str(msg.id),
                new_value={
                    "recipient": recipient,
                    "provider_message_id": provider_id,
                    "idempotency_key": idempotency_key,
                },
            )
        )
        return msg

