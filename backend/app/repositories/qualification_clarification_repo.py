import uuid
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc

from app.models.qualification_clarification import QualificationClarification
from app.models.enums import ClarificationStatus


class QualificationClarificationRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, clarification_id: uuid.UUID) -> Optional[QualificationClarification]:
        return (
            self.db.query(QualificationClarification)
            .filter(QualificationClarification.id == clarification_id)
            .first()
        )

    def get_active_for_field(
        self, lead_id: uuid.UUID, field_name: str
    ) -> Optional[QualificationClarification]:
        return (
            self.db.query(QualificationClarification)
            .filter(
                QualificationClarification.lead_id == lead_id,
                QualificationClarification.field_name == field_name,
                QualificationClarification.status.in_([
                    ClarificationStatus.OPEN,
                    ClarificationStatus.WAITING_FOR_TENANT,
                ]),
            )
            .order_by(desc(QualificationClarification.created_at))
            .first()
        )

    def get_latest_open_for_lead(self, lead_id: uuid.UUID) -> Optional[QualificationClarification]:
        return (
            self.db.query(QualificationClarification)
            .filter(
                QualificationClarification.lead_id == lead_id,
                QualificationClarification.status.in_([
                    ClarificationStatus.OPEN,
                    ClarificationStatus.WAITING_FOR_TENANT,
                ]),
            )
            .order_by(desc(QualificationClarification.created_at))
            .first()
        )

    def list_for_lead(self, lead_id: uuid.UUID, limit: int = 50) -> List[QualificationClarification]:
        return (
            self.db.query(QualificationClarification)
            .filter(QualificationClarification.lead_id == lead_id)
            .order_by(desc(QualificationClarification.created_at))
            .limit(limit)
            .all()
        )

    def create(self, data: Dict[str, Any]) -> QualificationClarification:
        clarification = QualificationClarification(
            id=data.get("id", uuid.uuid4()),
            lead_id=data["lead_id"],
            field_name=data["field_name"],
            reason=data["reason"],
            proposed_value=data.get("proposed_value"),
            status=data.get("status", ClarificationStatus.OPEN),
            attempt_count=data.get("attempt_count", 1),
            last_question_id=data.get("last_question_id"),
            resolved_value=data.get("resolved_value"),
        )
        self.db.add(clarification)
        self.db.commit()
        self.db.refresh(clarification)
        return clarification

    def update(
        self, clarification: QualificationClarification, updates: Dict[str, Any]
    ) -> QualificationClarification:
        for k, v in updates.items():
            if hasattr(clarification, k):
                setattr(clarification, k, v)
        self.db.commit()
        self.db.refresh(clarification)
        return clarification

    def resolve(
        self, clarification: QualificationClarification, resolved_value: Any
    ) -> QualificationClarification:
        clarification.status = ClarificationStatus.RESOLVED
        clarification.resolved_value = resolved_value
        clarification.resolved_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(clarification)
        return clarification

    def escalate(
        self, clarification: QualificationClarification
    ) -> QualificationClarification:
        clarification.status = ClarificationStatus.ESCALATED
        self.db.commit()
        self.db.refresh(clarification)
        return clarification

    def cancel(
        self, clarification: QualificationClarification
    ) -> QualificationClarification:
        clarification.status = ClarificationStatus.CANCELLED
        self.db.commit()
        self.db.refresh(clarification)
        return clarification

    def increment_attempt(
        self, clarification: QualificationClarification
    ) -> QualificationClarification:
        clarification.attempt_count = (clarification.attempt_count or 0) + 1
        self.db.commit()
        self.db.refresh(clarification)
        return clarification
