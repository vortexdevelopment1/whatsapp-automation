from typing import Dict, Optional, Any
from pydantic import BaseModel, Field
from app.models.enums import ConfidenceLevel, ConfidenceAction


class ConfidenceEvaluationResult(BaseModel):
    field: str
    confidence: float
    level: ConfidenceLevel
    action: ConfidenceAction
    reason: str
    normalized_value: Optional[Any] = None

    class Config:
        from_attributes = True

    def __getitem__(self, item: str):
        val = getattr(self, item)
        if hasattr(val, "value"):
            return val.value
        return val


class ConfidencePolicyConfig(BaseModel):
    default_high_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    default_medium_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    field_thresholds: Dict[str, float] = Field(
        default_factory=lambda: {
            "move_in_date": 0.95,
            "lease_duration_months": 0.95,
        }
    )
