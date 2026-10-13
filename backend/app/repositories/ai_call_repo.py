from datetime import datetime, timezone
from typing import List, Optional
import uuid
from sqlalchemy.orm import Session

from app.models.ai_call import AICall
from app.models.enums import AICallStatus, AITaskType


class AICallRepository:
    """Repository for querying and creating AI call telemetry records."""

    def __init__(self, db: Session):
        self.db = db

    def create(
        self,
        request_id: str,
        task_type: AITaskType,
        provider: str,
        model: str,
        prompt_name: Optional[str] = None,
        prompt_version: Optional[str] = None,
        lead_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        idempotency_key: Optional[str] = None,
        status: AICallStatus = AICallStatus.STARTED,
    ) -> AICall:
        call = AICall(
            request_id=request_id,
            lead_id=lead_id,
            conversation_id=conversation_id,
            task_type=task_type,
            provider=provider,
            model=model,
            prompt_name=prompt_name or "adhoc",
            prompt_version=prompt_version or "v1.0",
            status=status,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(call)
        self.db.commit()
        self.db.refresh(call)
        return call

    def mark_success(
        self,
        call: AICall,
        latency_ms: int,
        input_token_count: Optional[int] = None,
        output_token_count: Optional[int] = None,
        total_token_count: Optional[int] = None,
        estimated_cost_usd: Optional[float] = None,
    ) -> AICall:
        call.status = AICallStatus.SUCCESS
        call.latency_ms = latency_ms
        call.input_token_count = input_token_count
        call.output_token_count = output_token_count
        call.total_token_count = total_token_count
        call.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(call)
        return call


    def mark_failure(
        self,
        call: AICall,
        status: AICallStatus,
        error_type: str,
        error_message: str,
        latency_ms: Optional[int] = None,
    ) -> AICall:
        call.status = status
        call.error_type = error_type
        call.error_message = error_message
        call.latency_ms = latency_ms
        call.completed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(call)
        return call

    def get_by_request_id(self, request_id: str) -> Optional[AICall]:
        return self.db.query(AICall).filter(AICall.request_id == request_id).first()

    def list_calls(

        self,
        lead_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[uuid.UUID] = None,
        task_type: Optional[AITaskType] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> List[AICall]:
        query = self.db.query(AICall)
        if lead_id:
            query = query.filter(AICall.lead_id == lead_id)
        if conversation_id:
            query = query.filter(AICall.conversation_id == conversation_id)
        if task_type:
            query = query.filter(AICall.task_type == task_type)
        return query.order_by(AICall.created_at.desc()).offset(skip).limit(limit).all()

    def get_recent_stats(self) -> dict:
        """Helper to get last successful call and last failed call for integration status."""
        last_success = (
            self.db.query(AICall)
            .filter(AICall.status == AICallStatus.SUCCESS)
            .order_by(AICall.completed_at.desc())
            .first()
        )
        last_failed = (
            self.db.query(AICall)
            .filter(AICall.status.in_([AICallStatus.FAILED, AICallStatus.INVALID_OUTPUT]))
            .order_by(AICall.completed_at.desc())
            .first()
        )
        return {
            "last_success_at": last_success.completed_at if last_success else None,
            "last_failure_at": last_failed.completed_at if last_failed else None,
            "last_failure_error": last_failed.error_message if last_failed else None,
        }
