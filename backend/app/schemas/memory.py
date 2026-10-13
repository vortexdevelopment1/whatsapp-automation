import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field
from app.models.enums import SummaryGeneratedBy, QualificationStatus, QualificationMode


class StructuredSummary(BaseModel):
    qualification_status: str = "NOT_STARTED"
    completion_percentage: int = 0
    confirmed_requirements: Dict[str, Any] = Field(default_factory=dict)
    proposed_requirements: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    clarifications: List[str] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    human_review: bool = False
    ai_mode: str = "ACTIVE"
    last_intent: Optional[str] = None


class ConversationSummaryResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    summary_text: str
    structured_summary: Optional[Dict[str, Any]] = None
    summary_version: int
    last_message_id: Optional[uuid.UUID] = None
    generated_by: SummaryGeneratedBy
    ai_call_id: Optional[uuid.UUID] = None
    prompt_version: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class ConversationNoteCreate(BaseModel):
    note: str = Field(min_length=1, max_length=5000)


class ConversationNoteResponse(BaseModel):
    id: uuid.UUID
    lead_id: uuid.UUID
    conversation_id: Optional[uuid.UUID] = None
    author_id: str
    note: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardRequirementField(BaseModel):
    field_name: str
    label: str
    value: Any = None
    status: str  # CONFIRMED, PROPOSED, CLARIFICATION, MISSING, CONFLICT
    confidence_level: Optional[str] = None
    confidence: Optional[float] = None
    reason: Optional[str] = None


class QualificationDashboardResponse(BaseModel):
    lead_id: uuid.UUID
    lead_name: Optional[str] = None
    lead_phone: str
    qualification_status: QualificationStatus
    completion_percentage: int
    ai_mode: QualificationMode
    ai_paused: bool
    is_human_review: bool

    # Core Requirements
    requirements: Dict[str, Any] = Field(default_factory=dict)
    field_details: List[DashboardRequirementField] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    clarification_fields: List[str] = Field(default_factory=list)

    # Escalations & Clarifications
    clarifications: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    active_escalation: Optional[Dict[str, Any]] = None

    # Summary
    summary: Optional[ConversationSummaryResponse] = None

    # Next Expected Action
    next_action: Dict[str, Any] = Field(default_factory=dict)

    # Recent Message Timeline
    recent_messages: List[Dict[str, Any]] = Field(default_factory=list)

    # Operator Notes
    operator_notes: List[ConversationNoteResponse] = Field(default_factory=list)

    # Technical AI Activity
    last_ai_activity: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)


class SummaryRefreshResponse(BaseModel):
    success: bool
    summary: ConversationSummaryResponse
    refreshed_reason: str

    def __getitem__(self, item: str) -> Any:
        return getattr(self, item)
