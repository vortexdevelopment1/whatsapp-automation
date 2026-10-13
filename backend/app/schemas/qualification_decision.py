import uuid
from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import QualificationStatus


class QualificationDecisionEvaluateRequest(BaseModel):
    apply: bool = Field(default=False, description="Whether to commit state changes to database")
    override_decision: Optional[QualificationStatus] = Field(default=None, description="Human override target status")
    override_reason: Optional[str] = Field(default=None, description="Required justification when applying human override")


class QualificationDecisionResponse(BaseModel):
    id: Optional[uuid.UUID] = None
    lead_id: uuid.UUID
    tenant_requirement_id: Optional[uuid.UUID] = None
    decision: QualificationStatus
    reason_codes: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    blocking_fields: List[str] = Field(default_factory=list)
    completion_percentage: int
    rule_version: str
    applied: bool = False
    evaluated_by: str = "system"
    evaluation_source: str = "SYSTEM"
    override_reason: Optional[str] = None
    created_at: Optional[datetime] = None
    evaluated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    def __getitem__(self, item: str):
        val = getattr(self, item)
        if hasattr(val, "value"):
            return val.value
        return val

    def get(self, item: str, default=None):
        if hasattr(self, item):
            val = getattr(self, item)
            if hasattr(val, "value"):
                return val.value
            return val
        return default
