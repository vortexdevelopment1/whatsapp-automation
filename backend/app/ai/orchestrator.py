import asyncio
import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple, Type, TypeVar
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import AICallStatus, AITaskType
from app.ai.enums import ConfidenceLevel, TenantIntent
from app.ai.exceptions import (
    AIConfigurationError,
    AIError,
    AIInvalidResponseError,
    AIProviderError,
    AIRateLimitError,
    AISchemaValidationError,
    AITimeoutError,
)
from app.ai.prompts.base import PromptDefinition
from app.ai.prompts.registry import get_active_prompt
from app.ai.providers.base import AIProvider
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas import (
    AIRequest,
    AIResponse,
    AIUsage,
    IntentResult,
    QualificationAIContext,
    RequirementExtractionResult,
    QuestionResponseResult,
    ConversationSummaryResult,
    AgentResponseExtractionResult,
)
from app.repositories.ai_call_repo import AICallRepository

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AIOrchestrator:
    """
    Central AI Orchestration service for Module 3.
    Coordinates provider selection, prompt loading, bounded retries on transient errors,
    timeouts, structured response validation, telemetry, and call logging.
    
    CRITICAL SAFETY RULES:
    1. NEVER writes directly to tenant_requirements or leads tables.
    2. NEVER sends WhatsApp messages directly.
    3. NEVER logs sensitive API keys or credentials.
    """

    def __init__(
        self,
        provider: Optional[AIProvider] = None,
        provider_name: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout_seconds: Optional[float] = None,
        max_retries: Optional[int] = None,
    ):
        self.provider_name = (provider_name or settings.AI_PROVIDER).lower()
        self.model_name = model_name or settings.AI_MODEL
        self.timeout_seconds = timeout_seconds if timeout_seconds is not None else settings.AI_TIMEOUT_SECONDS
        self.max_retries = max_retries if max_retries is not None else settings.AI_MAX_RETRIES

        # If an explicit provider instance is passed (e.g. for testing), use it.
        # Otherwise, dynamically initialize the configured provider.
        if provider:
            self._provider = provider
        else:
            self._provider = self._init_provider(self.provider_name)

    def _init_provider(self, name: str) -> AIProvider:
        if name == "mock":
            return MockAIProvider()
        elif name == "openai":
            if not settings.AI_API_KEY:
                logger.warning("AI_API_KEY is not configured; falling back to MockAIProvider.")
                return MockAIProvider()
            return OpenAIProvider(
                api_key=settings.AI_API_KEY,
                base_url=settings.AI_API_BASE or "https://api.openai.com/v1",
                timeout_seconds=self.timeout_seconds,
                default_model=self.model_name,
            )
        else:
            logger.warning(f"Unknown AI provider '{name}'. Defaulting to MockAIProvider.")
            return MockAIProvider()

    def get_provider(self) -> AIProvider:
        return self._provider

    def set_provider(self, provider: AIProvider, name: str = "custom") -> None:
        self._provider = provider
        self.provider_name = name

    async def execute_structured(
        self,
        task_type: AITaskType,
        context: Optional[QualificationAIContext] = None,
        custom_prompt: Optional[str] = None,
        response_model: Optional[Type[T]] = None,
        prompt_name: Optional[str] = None,
        prompt_version: Optional[str] = None,
        idempotency_key: Optional[str] = None,
        db: Optional[Session] = None,
    ) -> AIResponse[T]:
        """
        Execute a structured AI call with full lifecycle:
        1. Select prompt & schema definition
        2. Render prompt from context
        3. Create AICall log (STARTED) if DB session provided
        4. Execute with bounded exponential retries on transient errors
        5. Validate structured response against target Pydantic model
        6. Record success/failure telemetry and call status in DB
        7. Return typed AIResponse[T]
        """
        request_id = f"ai_req_{uuid.uuid4().hex[:16]}"
        start_time = time.perf_counter()

        # 1. Resolve prompt definition
        prompt_def: Optional[PromptDefinition] = None
        if prompt_name:
            prompt_def = get_active_prompt(prompt_name)
        elif task_type == AITaskType.INTENT_CLASSIFICATION:
            prompt_def = get_active_prompt("intent_classification")
        elif task_type == AITaskType.REQUIREMENT_EXTRACTION:
            prompt_def = get_active_prompt("requirement_extraction")
        elif task_type == AITaskType.RESPONSE_GENERATION:
            prompt_def = get_active_prompt("qualification_question")
        elif task_type == AITaskType.CONVERSATION_SUMMARY:
            prompt_def = get_active_prompt("qualification_summary_v1")
        elif task_type == AITaskType.AGENT_RESPONSE_EXTRACTION:
            prompt_def = get_active_prompt("agent_response_extraction")

        # Resolve response model class
        target_model_cls = response_model
        if target_model_cls is None:
            if prompt_def and prompt_def.response_model_cls:
                target_model_cls = prompt_def.response_model_cls
            elif task_type == AITaskType.INTENT_CLASSIFICATION:
                target_model_cls = IntentResult
            elif task_type == AITaskType.REQUIREMENT_EXTRACTION:
                target_model_cls = RequirementExtractionResult
            elif task_type == AITaskType.RESPONSE_GENERATION:
                target_model_cls = QuestionResponseResult
            elif task_type == AITaskType.CONVERSATION_SUMMARY:
                target_model_cls = ConversationSummaryResult
            elif task_type == AITaskType.AGENT_RESPONSE_EXTRACTION:
                target_model_cls = AgentResponseExtractionResult
            else:
                raise AISchemaValidationError(f"No response model class configured for task {task_type}")


        # Render prompt text
        user_prompt = custom_prompt or ""
        if prompt_def and context:
            rendered = prompt_def.render(context)
            if custom_prompt:
                user_prompt = f"{custom_prompt}\n\n{rendered}"
            else:
                user_prompt = rendered
        elif not user_prompt and context:
            user_prompt = context.format_for_prompt()

        system_instruction = prompt_def.system_instruction if prompt_def else None
        active_prompt_name = prompt_def.name if prompt_def else (prompt_name or "adhoc")
        active_prompt_version = prompt_def.version if prompt_def else (prompt_version or "v1.0")

        # 2. Setup AI request
        ai_request = AIRequest(
            task_type=task_type,
            prompt=user_prompt,
            system_prompt=system_instruction,
            model=self.model_name,
            temperature=settings.AI_TEMPERATURE,
            max_tokens=settings.AI_MAX_OUTPUT_TOKENS,
            request_id=request_id,
            idempotency_key=idempotency_key,
        )

        # 3. Create initial AICall DB record if DB is provided
        ai_call_record = None
        call_repo = None
        if db is not None:
            try:
                call_repo = AICallRepository(db)
                ai_call_record = call_repo.create(
                    request_id=request_id,
                    task_type=task_type,
                    provider=self.provider_name,
                    model=self.model_name,
                    prompt_name=active_prompt_name,
                    prompt_version=active_prompt_version,
                    lead_id=(getattr(context, "lead_id", None) or (context.get("lead_id") if isinstance(context, dict) else None)) if context else None,
                    conversation_id=(getattr(context, "conversation_id", None) or (context.get("conversation_id") if isinstance(context, dict) else None)) if context else None,
                    idempotency_key=idempotency_key,
                    status=AICallStatus.STARTED,
                )
            except Exception as exc:
                logger.error(f"Failed to create initial AICall record: {exc}")

        # 4. Execute request with bounded retries for transient errors
        last_error: Optional[Exception] = None
        parsed_data = None
        usage = AIUsage()

        for attempt in range(self.max_retries + 1):
            try:
                # Wrap with asyncio.wait_for to enforce timeout strictly at orchestrator level
                parsed_data, raw_text, usage = await asyncio.wait_for(
                    self._provider.generate_structured(ai_request, target_model_cls),
                    timeout=self.timeout_seconds,
                )
                last_error = None
                break
            except asyncio.TimeoutError:
                last_error = AITimeoutError(
                    f"AI request timed out after {self.timeout_seconds}s (attempt {attempt + 1}/{self.max_retries + 1})"
                )
                logger.warning(f"AI timeout on attempt {attempt + 1}: {last_error}")
            except (AITimeoutError, AIRateLimitError, AIProviderError) as exc:
                last_error = exc
                logger.warning(f"Transient AI provider error on attempt {attempt + 1}: {exc}")
            except (AISchemaValidationError, AIInvalidResponseError, AIConfigurationError) as exc:
                # Non-transient errors: do not retry
                last_error = exc
                logger.error(f"Non-retryable AI error: {exc}")
                break
            except Exception as exc:
                # Unhandled unexpected error: normalize and do not retry blindly
                last_error = AIProviderError(f"Unexpected provider error: {exc}")
                logger.error(f"Unexpected provider failure: {exc}", exc_info=True)
                break

            # Backoff before retry
            if attempt < self.max_retries:
                backoff_delay = 0.1 * (2 ** attempt)
                await asyncio.sleep(backoff_delay)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        # 5. Handle result or failure logging
        if last_error is not None:
            status = AICallStatus.FAILED
            if isinstance(last_error, (AISchemaValidationError, AIInvalidResponseError)):
                status = AICallStatus.INVALID_OUTPUT

            if ai_call_record and call_repo:
                try:
                    call_repo.mark_failure(
                        call=ai_call_record,
                        status=status,
                        error_type=type(last_error).__name__,
                        error_message=str(last_error)[:500],
                        latency_ms=latency_ms,
                    )
                except Exception as exc:
                    logger.error(f"Failed to record AICall failure in DB: {exc}")

            raise last_error

        # Success path
        if ai_call_record and call_repo:
            try:
                call_repo.mark_success(
                    call=ai_call_record,
                    latency_ms=latency_ms,
                    input_token_count=usage.input_tokens,
                    output_token_count=usage.output_tokens,
                    total_token_count=usage.total_tokens,
                    estimated_cost_usd=usage.estimated_cost_usd,
                )
            except Exception as exc:
                logger.error(f"Failed to record AICall success in DB: {exc}")

        return AIResponse[T](
            task_type=task_type,
            model=self.model_name,
            provider=self.provider_name,
            prompt_version=active_prompt_version,
            request_id=request_id,
            data=parsed_data,
            usage=usage,
            latency_ms=latency_ms,
        )

    def classify_confidence_level(self, score: float) -> ConfidenceLevel:
        """Helper to map a numeric confidence (0.0 to 1.0) into a policy tier without binding business decisions."""
        if score >= 0.85:
            return ConfidenceLevel.HIGH
        elif score >= 0.60:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.LOW
