import uuid
from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict


class LeadRoutingDecisionBase(BaseModel):
    route_name: str
    reason: Any
    rule_version: Optional[str] = None
    manual_override: bool = False
    overridden_by: Optional[uuid.UUID] = None


class LeadRoutingDecisionCreate(LeadRoutingDecisionBase):
    lead_id: uuid.UUID


class LeadRoutingDecisionResponse(LeadRoutingDecisionBase):
    id: uuid.UUID
    lead_id: uuid.UUID
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
