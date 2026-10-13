import uuid
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.qualification_decision import QualificationDecision


class QualificationDecisionRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, decision_id: uuid.UUID) -> Optional[QualificationDecision]:
        return (
            self.db.query(QualificationDecision)
            .filter(QualificationDecision.id == decision_id)
            .first()
        )

    def get_latest_for_lead(self, lead_id: uuid.UUID) -> Optional[QualificationDecision]:
        return (
            self.db.query(QualificationDecision)
            .filter(QualificationDecision.lead_id == lead_id)
            .order_by(QualificationDecision.created_at.desc())
            .first()
        )

    def list_for_lead(self, lead_id: uuid.UUID, limit: int = 50) -> List[QualificationDecision]:
        return (
            self.db.query(QualificationDecision)
            .filter(QualificationDecision.lead_id == lead_id)
            .order_by(QualificationDecision.created_at.desc())
            .limit(limit)
            .all()
        )

    def create(self, data: dict) -> QualificationDecision:
        decision = QualificationDecision(**data)
        self.db.add(decision)
        self.db.commit()
        self.db.refresh(decision)
        return decision
