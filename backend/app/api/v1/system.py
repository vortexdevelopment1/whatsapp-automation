from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings
from app.models.enums import AITaskType
from app.ai.orchestrator import AIOrchestrator
from app.ai.providers.mock import MockAIProvider
from app.ai.providers.openai import OpenAIProvider
from app.ai.schemas import NormalizedMessage, QualificationAIContext
from app.repositories.ai_call_repo import AICallRepository

router = APIRouter(tags=["system", "ai"])


class AIHealthResponse(BaseModel):
    configured: bool
    provider: str
    model: str
    status: str
    timeout_seconds: float
    max_retries: int
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    last_failure_error: Optional[str] = None


class DevTestAIRequest(BaseModel):
    task_type: AITaskType = AITaskType.INTENT_CLASSIFICATION
    user_message: str = Field(..., description="Sample user message for structured analysis")
    provider_override: Optional[str] = Field(None, description="Optional 'mock' or 'openai'")


@router.get("/system/ai/health", response_model=AIHealthResponse)
def get_ai_health(db: Session = Depends(get_db)):
    """
    Check internal AI provider configuration and recent telemetry status.
    NEVER exposes secrets, API keys, or tenant credentials.
    """
    call_repo = AICallRepository(db)
    stats = call_repo.get_recent_stats()

    is_configured = False
    provider_name = settings.AI_PROVIDER.lower()

    if provider_name == "mock":
        is_configured = True
    elif provider_name == "openai":
        is_configured = bool(settings.AI_API_KEY and len(settings.AI_API_KEY.strip()) > 0)
    else:
        is_configured = False

    health_status = "READY" if is_configured else "UNCONFIGURED"

    return AIHealthResponse(
        configured=is_configured,
        provider=settings.AI_PROVIDER,
        model=settings.AI_MODEL,
        status=health_status,
        timeout_seconds=settings.AI_TIMEOUT_SECONDS,
        max_retries=settings.AI_MAX_RETRIES,
        last_success_at=stats.get("last_success_at"),
        last_failure_at=stats.get("last_failure_at"),
        last_failure_error=stats.get("last_failure_error"),
    )


@router.post("/dev/ai/test-structured-output")
async def dev_test_structured_output(
    payload: DevTestAIRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """
    Development-only test endpoint to verify structured AI output orchestration.
    - Disabled in production
    - Never modifies lead data or tenant requirements
    - Never sends WhatsApp messages
    """
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev AI test endpoints are disabled in production environment.",
        )
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Dev test endpoints require operator or admin role.",
        )

    # Initialize orchestrator
    orchestrator = AIOrchestrator()
    if payload.provider_override:
        if payload.provider_override.lower() == "mock":
            orchestrator.set_provider(MockAIProvider(), name="mock")
        elif payload.provider_override.lower() == "openai":
            if not settings.AI_API_KEY:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot override to OpenAI: AI_API_KEY is not configured.",
                )
            orchestrator.set_provider(
                OpenAIProvider(
                    api_key=settings.AI_API_KEY,
                    base_url=settings.AI_API_BASE or "https://api.openai.com/v1",
                    timeout_seconds=settings.AI_TIMEOUT_SECONDS,
                    default_model=settings.AI_MODEL,
                ),
                name="openai",
            )

    # Construct safe qualification context
    ctx = QualificationAIContext(
        recent_messages=[
            NormalizedMessage(role="tenant", text=payload.user_message)
        ]
    )

    try:
        response = await orchestrator.execute_structured(
            task_type=payload.task_type,
            context=ctx,
            db=db,
        )
        return {
            "task_type": response.task_type,
            "provider": response.provider,
            "model": response.model,
            "prompt_version": response.prompt_version,
            "request_id": response.request_id,
            "data": response.data.model_dump() if hasattr(response.data, "model_dump") else response.data,
            "usage": response.usage.model_dump(),
            "latency_ms": response.latency_ms,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI execution error: {str(exc)}",
        )


class DevExtractRequirementsRequest(BaseModel):
    text: str = Field(..., min_length=1, description="Tenant message text to extract requirements from")


@router.post("/dev/module3/extract")
async def dev_extract_requirements(
    payload: DevExtractRequirementsRequest,
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """
    Development-only text extraction endpoint for testing Module 3 understanding.
    - Disabled in production
    - Does NOT modify database records
    - Does NOT send WhatsApp messages
    """
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev endpoints are disabled in production environment.",
        )
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Dev test endpoints require operator or admin role.",
        )

    from app.services.tenant_message_understanding_service import TenantMessageUnderstandingService
    service = TenantMessageUnderstandingService(db)
    result = await service.extract_from_text(payload.text)
    return result.model_dump()


@router.post("/dev/module4/seed-inventory")
def dev_seed_inventory(
    x_user_role: Optional[str] = Header(None, alias="X-User-Role"),
    db: Session = Depends(get_db),
):
    """
    Seed safe synthetic demo property inventory fixtures.
    - Disabled in production
    """
    if settings.ENVIRONMENT.lower() == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev endpoints are disabled in production environment.",
        )
    if x_user_role in ("viewer", "unauthorized"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unauthorized: Dev test endpoints require operator or admin role.",
        )

    from app.db.seeds.property_seeds import seed_property_inventory
    result = seed_property_inventory(db)
    return {"status": "ok", "seeded": result}



