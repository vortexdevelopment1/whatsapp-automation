import uuid
from typing import Optional
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import EscalationStatus, EscalationReason


class EscalationCreateRequest(BaseModel):
    reason_code: EscalationReason = Field(default=EscalationReason.OPERATOR_TAKEOVER)
    description: Optional[str] = None
    created_by: str = Field(default="system")
    assigned_to: Optional[str] = None


class EscalationResolveRequest(BaseModel):
    resolution_notes: Optional[str] = None
    resolved_by: str = Field(default="operator")
    resume_ai: bool = Field(default=True)


class EscalationResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    reason_code: EscalationReason
    description: Optional[str] = None
    status: EscalationStatus
    assigned_to: Optional[str] = None
    created_by: str
    resolution_notes: Optional[str] = None
    resolved_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    def __getitem__(self, item: str):
        val = getattr(self, item)
        if hasattr(val, "value"):
            return val.value
        return val


class OperatorMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)
    operator_id: str = Field(..., min_length=1)
