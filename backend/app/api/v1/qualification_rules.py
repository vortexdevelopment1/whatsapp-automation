import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.deps import get_db
from app.schemas.tenant_requirement import (
    QualificationRuleResponse,
    QualificationRuleCreate,
)
from app.repositories.qualification_rule_repo import QualificationRuleRepository

router = APIRouter(prefix="/qualification-rules", tags=["qualification-rules"])


@router.get("", response_model=List[QualificationRuleResponse])
def list_qualification_rules(
    db: Session = Depends(get_db),
):
    repo = QualificationRuleRepository(db)
    # Ensure default rule is seeded if empty
    repo.get_active_rule()
    return repo.list_rules()


@router.get("/{rule_id}", response_model=QualificationRuleResponse)
def get_qualification_rule(
    rule_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    repo = QualificationRuleRepository(db)
    rule = repo.get_by_id(rule_id)
    if not rule:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Qualification rule with id '{rule_id}' not found.",
        )
    return rule


@router.post("", response_model=QualificationRuleResponse, status_code=status.HTTP_201_CREATED)
def create_qualification_rule(
    data: QualificationRuleCreate,
    db: Session = Depends(get_db),
):
    repo = QualificationRuleRepository(db)
    return repo.create(data.model_dump())
