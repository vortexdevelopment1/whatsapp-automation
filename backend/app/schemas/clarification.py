import uuid
from typing import Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field
from app.models.enums import ClarificationStatus


class ClarificationResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    field_name: str
    reason: str
    proposed_value: Optional[Any] = None
    status: ClarificationStatus
    attempt_count: int
    last_question_id: Optional[uuid.UUID] = None
    resolved_value: Optional[Any] = None
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    def __getitem__(self, item: str):
        val = getattr(self, item)
        if hasattr(val, "value"):
            return val.value
        return val


class ClarificationResolveRequest(BaseModel):
    resolved_value: Optional[Any] = None
    action: str = Field(default="CONFIRM", description="'CONFIRM' or 'REJECT' or 'CANCEL'")
    actor_id: str = Field(default="system")
