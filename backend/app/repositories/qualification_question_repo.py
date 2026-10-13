import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
from app.models.qualification_question import QualificationQuestion
from app.models.enums import QuestionAction, QuestionType, QualificationQuestionStatus


class QualificationQuestionRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        lead_id: uuid.UUID,
        action: QuestionAction,
        question_type: QuestionType,
        field_name: Optional[str] = None,
        question_text: Optional[str] = None,
        reason: Optional[str] = None,
        context_data: Optional[Dict[str, Any]] = None,
        source: str = "SYSTEM",
        message_id: Optional[uuid.UUID] = None,
        prompt_version: Optional[str] = None,
        clarification_attempts: int = 0,
        status: QualificationQuestionStatus = QualificationQuestionStatus.GENERATED,
    ) -> QualificationQuestion:
        record = QualificationQuestion(
            lead_id=lead_id,
            field_name=field_name,
            question_type=question_type,
            action=action,
            status=status,
            question_text=question_text,
            reason=reason,
            context_data=context_data or {},
            source=source,
            message_id=message_id,
            prompt_version=prompt_version,
            clarification_attempts=clarification_attempts,
        )
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def get_by_id(self, question_id: uuid.UUID) -> Optional[QualificationQuestion]:
        return (
            self.db.query(QualificationQuestion)
            .filter(QualificationQuestion.id == question_id)
            .first()
        )

    def get_latest_for_lead(self, lead_id: uuid.UUID) -> Optional[QualificationQuestion]:
        return (
            self.db.query(QualificationQuestion)
            .filter(QualificationQuestion.id == lead_id)
            .order_by(desc(QualificationQuestion.created_at))
            .first()
        )

    def list_for_lead(self, lead_id: uuid.UUID) -> List[QualificationQuestion]:
        return (
            self.db.query(QualificationQuestion)
            .filter(QualificationQuestion.lead_id == lead_id)
            .order_by(desc(QualificationQuestion.created_at))
            .all()
        )

    def count_attempts_for_field(
        self,
        lead_id: uuid.UUID,
        field_name: str,
        question_types: Optional[List[QuestionType]] = None,
    ) -> int:
        q = (
            self.db.query(QualificationQuestion)
            .filter(
                QualificationQuestion.lead_id == lead_id,
                QualificationQuestion.field_name == field_name,
            )
        )
        if question_types:
            q = q.filter(QualificationQuestion.question_type.in_(question_types))
        return q.count()

    def get_active_generated_question(
        self, lead_id: uuid.UUID, field_name: Optional[str]
    ) -> Optional[QualificationQuestion]:
        return (
            self.db.query(QualificationQuestion)
            .filter(
                QualificationQuestion.lead_id == lead_id,
                QualificationQuestion.field_name == field_name,
                QualificationQuestion.status == QualificationQuestionStatus.GENERATED,
            )
            .order_by(desc(QualificationQuestion.created_at))
            .first()
        )
