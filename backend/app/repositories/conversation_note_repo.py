import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.conversation_note import ConversationNote


class ConversationNoteRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_lead(self, lead_id: uuid.UUID, limit: int = 50) -> List[ConversationNote]:
        """Returns operator notes for a lead, latest first."""
        return (
            self.db.query(ConversationNote)
            .filter(ConversationNote.lead_id == lead_id)
            .order_by(desc(ConversationNote.created_at))
            .limit(limit)
            .all()
        )

    def create(self, lead_id: uuid.UUID, author_id: str, note: str, conversation_id: Optional[uuid.UUID] = None) -> ConversationNote:
        """Creates an operator note for a lead."""
        entry = ConversationNote(
            id=uuid.uuid4(),
            lead_id=lead_id,
            conversation_id=conversation_id,
            author_id=author_id,
            note=note,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
