import uuid
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.message import WhatsAppMessage
from app.schemas.message import MessageCreate


class MessageRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_provider_message_id(self, provider_message_id: str) -> Optional[WhatsAppMessage]:
        if not provider_message_id:
            return None
        return (
            self.db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.provider_message_id == provider_message_id)
            .first()
        )

    def create(self, data: MessageCreate) -> WhatsAppMessage:
        message = WhatsAppMessage(
            whatsapp_profile_id=data.whatsapp_profile_id,
            provider_message_id=data.provider_message_id,
            direction=data.direction,
            message_type=data.message_type,
            sender=data.sender,
            recipient=data.recipient,
            content=data.content,
            provider_status=data.provider_status,
            raw_payload=data.raw_payload,
        )
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_by_profile_id(
        self,
        whatsapp_profile_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> List[WhatsAppMessage]:
        return (
            self.db.query(WhatsAppMessage)
            .filter(WhatsAppMessage.whatsapp_profile_id == whatsapp_profile_id)
            .order_by(WhatsAppMessage.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
