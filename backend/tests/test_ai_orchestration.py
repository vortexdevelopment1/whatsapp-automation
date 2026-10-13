import asyncio
import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import AICallStatus, AITaskType
from app.ai.enums import ConfidenceLevel, TenantIntent
from app.ai.exceptions import (
    AIConfigurationError,
    AIInvalidResponseError,
    AIProviderError,
    AIRateLimitError,
    AISchemaValidationError,
    AITimeoutError,
)
from app.ai.orchestrator import AIOrchestrator
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas import (
    AIRequest,
    IntentResult,
    NormalizedMessage,
    QualificationAIContext,
    RequirementExtractionResult,
    RequirementFieldExtraction,
)
from app.models.ai_call import AICall
from app.models.lead import Lead
from app.models.tenant_requirement import TenantRequirement
from app.repositories.ai_call_repo import AICallRepository


# =====================================================================
# 1. Configuration & Provider Initialization Tests
# =====================================================================

def test_missing_api_key_openai_provider():
    """OpenAIProvider must refuse to initialize without an API key."""
    with pytest.raises(AIConfigurationError) as exc_info:
        OpenAIProvider(api_key=None)
    assert "OpenAI API key is missing" in str(exc_info.value)


def test_mock_provider_configuration():
    """MockAIProvider initializes cleanly and supports custom modes."""
    provider = MockAIProvider(mode="SUCCESS")
    assert provider.mode == "SUCCESS"
    provider.set_mode("TIMEOUT")
    assert provider.mode == "TIMEOUT"


def test_orchestrator_initialization_with_mock():
    """Orchestrator can initialize with Mock provider as default."""
    orchestrator = AIOrchestrator(provider_name="mock")
    assert isinstance(orchestrator.get_provider(), MockAIProvider)


# =====================================================================
# 2. Mock Provider Deterministic Scenarios
# =====================================================================

@pytest.mark.asyncio
async def test_mock_provider_success():
    provider = MockAIProvider(mode="SUCCESS")
    req = AIRequest(task_type=AITaskType.INTENT_CLASSIFICATION, prompt="I want a 2 room unit")
    result, raw, usage = await provider.generate_structured(req, IntentResult)
    assert isinstance(result, IntentResult)
    assert result.intent == TenantIntent.PROVIDE_REQUIREMENTS
    assert 0.0 <= result.confidence <= 1.0
    assert usage.total_tokens > 0


@pytest.mark.asyncio
async def test_mock_provider_timeout():
    provider = MockAIProvider(mode="TIMEOUT")
    req = AIRequest(task_type=AITaskType.INTENT_CLASSIFICATION, prompt="Test")
    with pytest.raises(AITimeoutError):
        await provider.generate_structured(req, IntentResult)


@pytest.mark.asyncio
async def test_mock_provider_rate_limit():
    provider = MockAIProvider(mode="RATE_LIMIT")
    req = AIRequest(task_type=AITaskType.INTENT_CLASSIFICATION, prompt="Test")
    with pytest.raises(AIRateLimitError):
        await provider.generate_structured(req, IntentResult)


@pytest.mark.asyncio
async def test_mock_provider_provider_error():
    provider = MockAIProvider(mode="PROVIDER_ERROR")
    req = AIRequest(task_type=AITaskType.INTENT_CLASSIFICATION, prompt="Test")
    with pytest.raises(AIProviderError):
        await provider.generate_structured(req, IntentResult)


@pytest.mark.asyncio
async def test_mock_provider_invalid_output():
    provider = MockAIProvider(mode="INVALID_OUTPUT")
    req = AIRequest(task_type=AITaskType.INTENT_CLASSIFICATION, prompt="Test")
    with pytest.raises(AIInvalidResponseError):
        await provider.generate_structured(req, IntentResult)


# =====================================================================
# 3. Structured Output & Schema Validation Tests
# =====================================================================

def test_intent_result_valid():
    valid = IntentResult(intent=TenantIntent.PROVIDE_REQUIREMENTS, confidence=0.95)
    assert valid.intent == "PROVIDE_REQUIREMENTS"
    assert valid.confidence == 0.95


def test_intent_result_invalid_intent():
    with pytest.raises(ValidationError):
        IntentResult(intent="ARBITRARY_INTENT_NOT_ALLOWED", confidence=0.90)  # type: ignore


def test_intent_result_confidence_bounds():
    with pytest.raises(ValidationError):
        IntentResult(intent=TenantIntent.GREETING, confidence=-0.1)

    with pytest.raises(ValidationError):
        IntentResult(intent=TenantIntent.GREETING, confidence=1.5)


def test_requirement_extraction_schema_valid():
    sample = {
        "intent": "PROVIDE_REQUIREMENTS",
        "fields": {
            "preferred_locations": {
                "value": ["Novena", "Toa Payoh"],
                "confidence": 0.98,
                "explicit": True,
                "needs_confirmation": False,
            },
            "budget_max": {
                "value": 3500,
                "confidence": 0.92,
                "explicit": True,
                "needs_confirmation": False,
            },
        },
        "needs_clarification": True,
        "clarification_fields": ["move_in_date"],
        "message_summary": "Looking for Novena/Toa Payoh under 3500.",
    }
    extracted = RequirementExtractionResult.model_validate(sample)
    assert extracted.intent == TenantIntent.PROVIDE_REQUIREMENTS
    assert extracted.fields["preferred_locations"].value == ["Novena", "Toa Payoh"]
    assert extracted.needs_clarification is True
    assert "move_in_date" in extracted.clarification_fields


def test_requirement_field_confidence_bounds():
    with pytest.raises(ValidationError):
        RequirementFieldExtraction(value=3000, confidence=1.2)


# =====================================================================
# 4. Orchestrator Execution, Retries, and Timeouts
# =====================================================================

@pytest.mark.asyncio
async def test_orchestrator_successful_execution(db: Session):
    mock = MockAIProvider(mode="SUCCESS")
    orchestrator = AIOrchestrator(provider=mock, max_retries=1)

    ctx = QualificationAIContext(
        recent_messages=[NormalizedMessage(role="tenant", text="Hi, need 2 bedroom condo in Novena")]
    )

    response = await orchestrator.execute_structured(
        task_type=AITaskType.INTENT_CLASSIFICATION,
        context=ctx,
        db=db,
    )

    assert response.task_type == AITaskType.INTENT_CLASSIFICATION
    assert response.request_id.startswith("ai_req_")
    assert response.prompt_version == "v1.0"
    assert response.data.intent == TenantIntent.PROVIDE_REQUIREMENTS
    assert response.usage.total_tokens > 0
    assert response.latency_ms >= 0

    # Verify DB logging
    call = db.query(AICall).filter(AICall.request_id == response.request_id).first()
    assert call is not None
    assert call.status == AICallStatus.SUCCESS
    assert call.latency_ms == response.latency_ms
    assert call.prompt_name == "intent_classification"


@pytest.mark.asyncio
async def test_orchestrator_retry_exhaustion(db: Session):
    """When a transient error persists, orchestrator retries up to max_retries and records failure."""
    mock = MockAIProvider(mode="PROVIDER_ERROR")
    orchestrator = AIOrchestrator(provider=mock, max_retries=2, timeout_seconds=2.0)

    with pytest.raises(AIProviderError):
        await orchestrator.execute_structured(
            task_type=AITaskType.INTENT_CLASSIFICATION,
            custom_prompt="Hello",
            db=db,
        )

    # 1 initial + 2 retries = 3 calls
    assert len(mock.call_history) == 3

    # Verify DB call record marked as FAILED
    call = db.query(AICall).filter(AICall.task_type == AITaskType.INTENT_CLASSIFICATION).order_by(AICall.created_at.desc()).first()
    assert call is not None
    assert call.status == AICallStatus.FAILED
    assert call.error_type == "AIProviderError"


@pytest.mark.asyncio
async def test_orchestrator_non_retryable_error_does_not_retry(db: Session):
    """Invalid output / schema mismatch should NOT retry endlessly."""
    mock = MockAIProvider(mode="INVALID_OUTPUT")
    orchestrator = AIOrchestrator(provider=mock, max_retries=3)

    with pytest.raises(AIInvalidResponseError):
        await orchestrator.execute_structured(
            task_type=AITaskType.INTENT_CLASSIFICATION,
            custom_prompt="Test",
            db=db,
        )

    # Only 1 attempt because it is non-retryable
    assert len(mock.call_history) == 1

    call = db.query(AICall).order_by(AICall.created_at.desc()).first()
    assert call is not None
    assert call.status == AICallStatus.INVALID_OUTPUT


@pytest.mark.asyncio
async def test_orchestrator_timeout_enforcement(db: Session):
    """Strict timeout enforcement at orchestrator level."""
    mock = MockAIProvider(mode="TIMEOUT")
    orchestrator = AIOrchestrator(provider=mock, max_retries=1, timeout_seconds=0.5)

    with pytest.raises(AITimeoutError):
        await orchestrator.execute_structured(
            task_type=AITaskType.INTENT_CLASSIFICATION,
            custom_prompt="Test timeout",
            db=db,
        )

    call = db.query(AICall).order_by(AICall.created_at.desc()).first()
    assert call is not None
    assert call.status == AICallStatus.FAILED
    assert "AITimeoutError" in call.error_type


def test_confidence_level_classification():
    orchestrator = AIOrchestrator(provider_name="mock")
    assert orchestrator.classify_confidence_level(0.95) == ConfidenceLevel.HIGH
    assert orchestrator.classify_confidence_level(0.85) == ConfidenceLevel.HIGH
    assert orchestrator.classify_confidence_level(0.75) == ConfidenceLevel.MEDIUM
    assert orchestrator.classify_confidence_level(0.60) == ConfidenceLevel.MEDIUM
    assert orchestrator.classify_confidence_level(0.40) == ConfidenceLevel.LOW


# =====================================================================
# 5. Strict Safety & Boundary Tests
# =====================================================================

@pytest.mark.asyncio
async def test_ai_layer_does_not_modify_database_entities(db: Session):
    """
    MANDATORY RULE: The AI orchestrator layer must NEVER write directly to
    leads or tenant_requirements tables.
    """
    initial_leads_count = db.query(Lead).count()
    initial_reqs_count = db.query(TenantRequirement).count()

    mock = MockAIProvider(mode="SUCCESS")
    orchestrator = AIOrchestrator(provider=mock)

    ctx = QualificationAIContext(
        recent_messages=[NormalizedMessage(role="tenant", text="Budget is 5000")]
    )

    response = await orchestrator.execute_structured(
        task_type=AITaskType.REQUIREMENT_EXTRACTION,
        context=ctx,
        db=db,
    )

    assert response.data is not None

    # Verify counts have NOT changed
    assert db.query(Lead).count() == initial_leads_count
    assert db.query(TenantRequirement).count() == initial_reqs_count


# =====================================================================
# 6. HTTP API Endpoints & Security Tests
# =====================================================================

def test_ai_health_endpoint_does_not_leak_secrets(client):
    """GET /api/system/ai/health returns status and config without secrets."""
    resp = client.get("/api/system/ai/health")
    assert resp.status_code == 200
    data = resp.json()

    assert "configured" in data
    assert "provider" in data
    assert "model" in data
    assert "status" in data
    assert "timeout_seconds" in data
    assert "max_retries" in data

    # Verify NO secrets are returned
    assert "api_key" not in data
    assert "secret" not in data
    assert "token" not in data


def test_dev_test_structured_output_endpoint(client):
    """POST /api/dev/ai/test-structured-output executes orchestrator cleanly."""
    resp = client.post(
        "/api/dev/ai/test-structured-output",
        json={
            "task_type": "INTENT_CLASSIFICATION",
            "user_message": "Hello, I am looking for a 3-bedroom place in Marina Bay.",
            "provider_override": "mock",
        },
    )
    assert resp.status_code == 200
    data = resp.json()

    assert data["task_type"] == "INTENT_CLASSIFICATION"
    assert data["provider"] == "mock"
    assert "request_id" in data
    assert "data" in data
    assert data["data"]["intent"] == "PROVIDE_REQUIREMENTS"
    assert data["usage"]["total_tokens"] > 0
