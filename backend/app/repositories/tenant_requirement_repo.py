import uuid
from typing import Optional, List, Any
from decimal import Decimal
from sqlalchemy.orm import Session
from app.models.tenant_requirement import TenantRequirement
from app.models.tenant_requirement_history import TenantRequirementHistory
from app.models.enums import RequirementFieldStatus, RequirementSourceType


class TenantRequirementRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, req_id: uuid.UUID) -> Optional[TenantRequirement]:
        return self.db.query(TenantRequirement).filter(TenantRequirement.id == req_id).first()

    def get_by_lead_id(self, lead_id: uuid.UUID) -> Optional[TenantRequirement]:
        return self.db.query(TenantRequirement).filter(TenantRequirement.lead_id == lead_id).first()

    def create(self, lead_id: uuid.UUID, data: dict) -> TenantRequirement:
        req = TenantRequirement(lead_id=lead_id, **data)
        self.db.add(req)
        self.db.commit()
        self.db.refresh(req)
        return req

    def update(self, req: TenantRequirement, update_dict: dict) -> TenantRequirement:
        for key, value in update_dict.items():
            if hasattr(req, key):
                setattr(req, key, value)
        self.db.commit()
        self.db.refresh(req)
        return req

    def add_history(
        self,
        tenant_requirement_id: uuid.UUID,
        field_name: str,
        value: Any,
        status: RequirementFieldStatus = RequirementFieldStatus.CONFIRMED,
        source_type: RequirementSourceType = RequirementSourceType.HUMAN_OPERATOR,
        confidence: Optional[Decimal] = None,
        source_message_id: Optional[uuid.UUID] = None,
    ) -> TenantRequirementHistory:
        if isinstance(value, Decimal):
            value = float(value)
        elif hasattr(value, "isoformat"):
            value = value.isoformat()

        history = TenantRequirementHistory(
            tenant_requirement_id=tenant_requirement_id,
            field_name=field_name,
            value=value,
            status=status,
            source_type=source_type,
            confidence=confidence,
            source_message_id=source_message_id,
        )
        self.db.add(history)
        self.db.commit()
        self.db.refresh(history)
        return history

    def supersede_active_history(self, tenant_requirement_id: uuid.UUID, field_name: str) -> None:
        active_entries = (
            self.db.query(TenantRequirementHistory)
            .filter(
                TenantRequirementHistory.tenant_requirement_id == tenant_requirement_id,
                TenantRequirementHistory.field_name == field_name,
                TenantRequirementHistory.status.in_([RequirementFieldStatus.CONFIRMED, RequirementFieldStatus.PROPOSED]),
            )
            .all()
        )
        for entry in active_entries:
            entry.status = RequirementFieldStatus.SUPERSEDED
        self.db.commit()

    def list_history(self, tenant_requirement_id: uuid.UUID) -> List[TenantRequirementHistory]:
        return (
            self.db.query(TenantRequirementHistory)
            .filter(TenantRequirementHistory.tenant_requirement_id == tenant_requirement_id)
            .order_by(TenantRequirementHistory.created_at.desc())
            .all()
        )
