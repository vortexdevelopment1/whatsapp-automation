from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from app.models.message_ai_processing import MessageAIProcessing
from app.models.enums import MessageAIProcessingStatus


class MessageAIProcessingRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_message_id(self, message_id: uuid.UUID) -> Optional[MessageAIProcessing]:
        return (
            self.db.query(MessageAIProcessing)
            .filter(MessageAIProcessing.message_id == message_id)
            .first()
        )

    def get_by_id(self, processing_id: uuid.UUID) -> Optional[MessageAIProcessing]:
        return (
            self.db.query(MessageAIProcessing)
            .filter(MessageAIProcessing.id == processing_id)
            .first()
        )

    def create(
        self,
        message_id: uuid.UUID,
        lead_id: uuid.UUID,
        ai_call_id: Optional[uuid.UUID] = None,
        intent: Optional[str] = None,
        intent_confidence: Optional[float] = None,
        status: MessageAIProcessingStatus = MessageAIProcessingStatus.PROCESSED,
        accepted_fields: Optional[List[str]] = None,
        proposed_fields: Optional[List[str]] = None,
        rejected_fields: Optional[List[str]] = None,
        clarification_fields: Optional[List[str]] = None,
        raw_extraction: Optional[Dict[str, Any]] = None,
        message_summary: Optional[str] = None,
        error_message: Optional[str] = None,
        response_message_id: Optional[uuid.UUID] = None,
    ) -> MessageAIProcessing:
        record = MessageAIProcessing(
            message_id=message_id,
            lead_id=lead_id,
            ai_call_id=ai_call_id,
            intent=intent,
            intent_confidence=intent_confidence,
            status=status,
            accepted_fields=accepted_fields or [],
            proposed_fields=proposed_fields or [],
            rejected_fields=rejected_fields or [],
            clarification_fields=clarification_fields or [],
            raw_extraction=raw_extraction,
            message_summary=message_summary,
            error_message=error_message,
            response_message_id=response_message_id,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update_response_message(
        self,
        processing_id: uuid.UUID,
        response_message_id: uuid.UUID,
        status: Optional[MessageAIProcessingStatus] = None,
    ) -> Optional[MessageAIProcessing]:
        record = self.get_by_id(processing_id)
        if record:
            record.response_message_id = response_message_id
            if status:
                record.status = status
            record.updated_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(record)
        return record

    def list_by_lead_id(
        self, lead_id: uuid.UUID, skip: int = 0, limit: int = 50
    ) -> List[MessageAIProcessing]:
        return (
            self.db.query(MessageAIProcessing)
            .filter(MessageAIProcessing.lead_id == lead_id)
            .order_by(MessageAIProcessing.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_latest_for_lead(self, lead_id: uuid.UUID) -> Optional[MessageAIProcessing]:
        return (
            self.db.query(MessageAIProcessing)
            .filter(MessageAIProcessing.lead_id == lead_id)
            .order_by(MessageAIProcessing.created_at.desc())
            .first()
        )

