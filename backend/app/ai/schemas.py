import uuid
from typing import Optional, List, Dict, Any, Type, Generic, TypeVar
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.models.enums import AITaskType, AICallStatus, QuestionAction, QuestionType
from app.ai.enums import TenantIntent, MessageRole, ConfidenceLevel

T = TypeVar("T")


class NormalizedMessage(BaseModel):
    role: MessageRole
    text: str
    timestamp: Optional[str] = None
    message_id: Optional[str] = None

    @field_validator("role", mode="before")
    @classmethod
    def normalize_role(cls, v: Any) -> Any:
        if isinstance(v, str):
            clean = v.strip().upper()
            if hasattr(MessageRole, clean):
                return MessageRole[clean]
        return v


class QualificationAIContext(BaseModel):
    lead_id: Optional[uuid.UUID] = None
    conversation_id: Optional[uuid.UUID] = None
    qualification_status: Optional[str] = None
    tenant_requirements: Optional[Dict[str, Any]] = None
    missing_required_fields: Optional[List[str]] = None
    conversation_summary: Optional[str] = None
    recent_messages: List[NormalizedMessage] = Field(default_factory=list)
    agent_context: Optional[Dict[str, Any]] = None
    route: Optional[str] = None
    language: Optional[str] = "en"

    def format_for_prompt(self) -> str:
        parts = []
        if self.recent_messages:
            parts.append("Recent Conversation:")
            for msg in self.recent_messages:
                parts.append(f"- {msg.role.value}: {msg.text}")
        if self.missing_required_fields:
            parts.append(f"Missing Fields: {', '.join(self.missing_required_fields)}")
        if self.conversation_summary:
            parts.append(f"Summary: {self.conversation_summary}")
        return "\n".join(parts) if parts else "No recent messages."


class AIUsage(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: Optional[float] = None


class AIRequest(BaseModel):
    task_type: AITaskType
    prompt: str = ""
    system_prompt: Optional[str] = None
    prompt_name: str = "adhoc"
    prompt_version: str = "v1.0"
    model: Optional[str] = None
    context: QualificationAIContext = Field(default_factory=QualificationAIContext)
    user_input: Optional[str] = None
    response_schema: Optional[Any] = None
    idempotency_key: Optional[str] = None
    request_id: Optional[str] = None
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class AIResponse(BaseModel, Generic[T]):
    request_id: str
    task_type: AITaskType
    provider: str
    model: str
    prompt_name: str = "adhoc"
    prompt_version: str = "v1.0"
    data: Optional[T] = None
    raw_text: Optional[str] = None
    usage: AIUsage = Field(default_factory=AIUsage)
    latency_ms: int = 0
    status: AICallStatus = AICallStatus.SUCCESS

    model_config = ConfigDict(arbitrary_types_allowed=True)



class IntentResult(BaseModel):
    intent: TenantIntent
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: Optional[str] = None

    @property
    def confidence_level(self) -> ConfidenceLevel:
        if self.confidence >= 0.85:
            return ConfidenceLevel.HIGH
        elif self.confidence >= 0.60:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW


class RequirementFieldExtraction(BaseModel):
    value: Any
    confidence: float = Field(ge=0.0, le=1.0)
    explicit: bool = True
    needs_confirmation: bool = False

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("confidence must be between 0.0 and 1.0")
        return v


class RequirementExtractionResult(BaseModel):
    intent: TenantIntent = TenantIntent.PROVIDE_REQUIREMENTS
    fields: Dict[str, RequirementFieldExtraction] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_fields: List[str] = Field(default_factory=list)
    message_summary: Optional[str] = None


class QuestionInstruction(BaseModel):
    action: QuestionAction
    field: Optional[str] = None
    question_type: Optional[QuestionType] = None
    reason: str
    context: Dict[str, Any] = Field(default_factory=dict)


class QuestionResponseResult(BaseModel):
    reply_text: str = Field(min_length=1)
    target_field: str
    prompt_version: str = "qualification_question_v1"


class NextQuestionResponse(BaseModel):
    lead_id: uuid.UUID
    action: QuestionAction
    field: Optional[str] = None
    question_type: Optional[QuestionType] = None
    question_text: Optional[str] = None
    fallback_used: bool = False
    reason: str
    completion_percentage: int
    completed_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    clarification_fields: List[str] = Field(default_factory=list)


class QualificationPreviewResponse(BaseModel):
    lead_id: uuid.UUID
    completion_percentage: int
    completed_fields: List[str] = Field(default_factory=list)
    missing_fields: List[str] = Field(default_factory=list)
    clarification_fields: List[str] = Field(default_factory=list)
    next_question: Optional[Dict[str, Any]] = None


class ConversationSummaryResult(BaseModel):
    summary_text: str = Field(min_length=1)
    confirmed_requirements: Dict[str, Any] = Field(default_factory=dict)
    missing_fields: List[str] = Field(default_factory=list)
    clarification_fields: List[str] = Field(default_factory=list)
    prompt_version: str = "qualification_summary_v1"


class AgentResponseFieldExtraction(BaseModel):
    value: Any
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    explicit: bool = True
    needs_confirmation: bool = False


class AgentResponseExtractionResult(BaseModel):
    intent: str = "AVAILABLE"
    fields: Dict[str, AgentResponseFieldExtraction] = Field(default_factory=dict)
    needs_clarification: bool = False
    clarification_reasons: List[str] = Field(default_factory=list)
    raw_summary: Optional[str] = None
    overall_confidence: float = Field(ge=0.0, le=1.0, default=1.0)


