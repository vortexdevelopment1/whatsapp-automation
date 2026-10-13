import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.conversation_summary import ConversationSummary
from app.models.enums import SummaryGeneratedBy


class ConversationSummaryRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_latest_for_lead(self, lead_id: uuid.UUID) -> Optional[ConversationSummary]:
        """Returns the most recent conversation summary for a lead."""
        return (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.lead_id == lead_id)
            .order_by(desc(ConversationSummary.summary_version))
            .first()
        )

    def list_for_lead(self, lead_id: uuid.UUID, limit: int = 10) -> List[ConversationSummary]:
        """Returns history of conversation summaries for a lead."""
        return (
            self.db.query(ConversationSummary)
            .filter(ConversationSummary.lead_id == lead_id)
            .order_by(desc(ConversationSummary.summary_version))
            .limit(limit)
            .all()
        )

    def create(self, data: Dict[str, Any]) -> ConversationSummary:
        """Creates a new conversation summary version."""
        lead_id = data["lead_id"]
        latest = self.get_latest_for_lead(lead_id)
        next_version = (latest.summary_version + 1) if latest else 1

        summary = ConversationSummary(
            id=data.get("id", uuid.uuid4()),
            lead_id=lead_id,
            conversation_id=data.get("conversation_id"),
            summary_text=data["summary_text"],
            structured_summary=data.get("structured_summary"),
            summary_version=data.get("summary_version", next_version),
            last_message_id=data.get("last_message_id"),
            generated_by=data.get("generated_by", SummaryGeneratedBy.SYSTEM),
            ai_call_id=data.get("ai_call_id"),
            prompt_version=data.get("prompt_version"),
        )
        self.db.add(summary)
        self.db.commit()
        self.db.refresh(summary)
        return summary
