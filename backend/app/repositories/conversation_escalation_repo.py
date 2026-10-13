import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.conversation_escalation import ConversationEscalation
from app.models.enums import EscalationStatus, EscalationReason


class ConversationEscalationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, escalation_id: uuid.UUID) -> Optional[ConversationEscalation]:
        return (
            self.db.query(ConversationEscalation)
            .filter(ConversationEscalation.id == escalation_id)
            .first()
        )

    def get_latest_open_for_lead(
        self, lead_id: uuid.UUID
    ) -> Optional[ConversationEscalation]:
        return (
            self.db.query(ConversationEscalation)
            .filter(
                ConversationEscalation.lead_id == lead_id,
                ConversationEscalation.status.in_([
                    EscalationStatus.OPEN,
                    EscalationStatus.ASSIGNED,
                ]),
            )
            .order_by(desc(ConversationEscalation.created_at))
            .first()
        )

    def list_all(
        self,
        status: Optional[EscalationStatus] = None,
        lead_id: Optional[uuid.UUID] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[ConversationEscalation]:
        q = self.db.query(ConversationEscalation)
        if status:
            q = q.filter(ConversationEscalation.status == status)
        if lead_id:
            q = q.filter(ConversationEscalation.lead_id == lead_id)
        return (
            q.order_by(desc(ConversationEscalation.created_at))
            .offset(offset)
            .limit(limit)
            .all()
        )

    def list_for_lead(
        self, lead_id: uuid.UUID, limit: int = 50
    ) -> List[ConversationEscalation]:
        return (
            self.db.query(ConversationEscalation)
            .filter(ConversationEscalation.lead_id == lead_id)
            .order_by(desc(ConversationEscalation.created_at))
            .limit(limit)
            .all()
        )

    def create(self, data: Dict[str, Any]) -> ConversationEscalation:
        escalation = ConversationEscalation(
            id=data.get("id", uuid.uuid4()),
            lead_id=data["lead_id"],
            conversation_id=data.get("conversation_id"),
            reason_code=data["reason_code"],
            description=data.get("description"),
            status=data.get("status", EscalationStatus.OPEN),
            assigned_to=data.get("assigned_to"),
            created_by=data.get("created_by", "system"),
            resolution_notes=data.get("resolution_notes"),
        )
        self.db.add(escalation)
        self.db.commit()
        self.db.refresh(escalation)
        return escalation

    def update(
        self, escalation: ConversationEscalation, updates: Dict[str, Any]
    ) -> ConversationEscalation:
        for k, v in updates.items():
            if hasattr(escalation, k):
                setattr(escalation, k, v)
        self.db.commit()
        self.db.refresh(escalation)
        return escalation

    def resolve(
        self, escalation: ConversationEscalation, resolution_notes: Optional[str] = None
    ) -> ConversationEscalation:
        escalation.status = EscalationStatus.RESOLVED
        escalation.resolution_notes = resolution_notes
        escalation.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(escalation)
        return escalation
