import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.message import MessageCreate, MessageResponse
from app.models.enums import MessageDirection, MessageType
from app.repositories.whatsapp_repo import WhatsAppRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditLogCreate
from pydantic import BaseModel, Field

router = APIRouter(prefix="/agents/{agent_id}/messages", tags=["messages"])


class SendTestMessageInput(BaseModel):
    recipient: str = Field(..., description="Recipient phone number")
    content: str = Field(..., min_length=1, description="Message content")
    message_type: MessageType = MessageType.TEXT


@router.get("", response_model=List[MessageResponse])
def list_agent_messages(
    agent_id: uuid.UUID,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    wa_repo = WhatsAppRepository(db)
    profile = wa_repo.get_by_agent_id(agent_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"WhatsApp profile not found for agent {agent_id}"
        )
    msg_repo = MessageRepository(db)
    return msg_repo.list_by_profile_id(profile.id, skip=skip, limit=limit)


@router.post("/test", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def send_test_message(
    agent_id: uuid.UUID,
    data: SendTestMessageInput,
    db: Session = Depends(get_db),
):
    wa_repo = WhatsAppRepository(db)
    profile = wa_repo.get_or_create_for_agent(agent_id)
    msg_repo = MessageRepository(db)
    audit_repo = AuditRepository(db)

    # In Phase 2/Module 1 console: records outbound test message
    mock_provider_id = f"wamid.test_{uuid.uuid4().hex[:12]}"
    created = msg_repo.create(
        MessageCreate(
            whatsapp_profile_id=profile.id,
            provider_message_id=mock_provider_id,
            direction=MessageDirection.OUTBOUND,
            message_type=data.message_type,
            sender=profile.display_phone_number or "+6590000000",
            recipient=data.recipient,
            content=data.content,
            provider_status="sent",
            raw_payload={"mock_send": True, "provider_id": mock_provider_id},
        )
    )

    audit_repo.log(
        AuditLogCreate(
            actor_id="admin",
            action="TEST_MESSAGE_SENT",
            entity_type="WhatsAppMessage",
            entity_id=str(created.id),
            new_value={"recipient": data.recipient, "provider_message_id": mock_provider_id},
        )
    )

    return created
