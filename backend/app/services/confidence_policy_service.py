from typing import Dict, Optional, Any, Tuple
from app.models.enums import ConfidenceLevel, ConfidenceAction
from app.schemas.confidence import ConfidenceEvaluationResult, ConfidencePolicyConfig


HIGH_CONFIDENCE_THRESHOLD = 0.85
MEDIUM_CONFIDENCE_THRESHOLD = 0.60
LOW_CONFIDENCE_THRESHOLD = 0.30


class ConfidencePolicyService:
    """
    Module 3 Phase 7: Centralized Confidence Policy Service.
    Enforces deterministic confidence thresholds across all qualification fields.
    Guarantees that high confidence alone does NOT accept a value without deterministic validation.
    """

    DEFAULT_HIGH_THRESHOLD = 0.85
    DEFAULT_MEDIUM_THRESHOLD = 0.60

    DEFAULT_FIELD_THRESHOLDS = {
        "move_in_date": 0.95,
        "lease_duration_months": 0.95,
        "budget_max": 0.85,
        "occupants": 0.85,
        "preferred_locations": 0.85,
        "property_type": 0.85,
    }

    def __init__(self, config: Optional[ConfidencePolicyConfig] = None):
        self.config = config or ConfidencePolicyConfig()

    def get_thresholds(self, field_name: str) -> Tuple[float, float]:
        """Returns (high_threshold, medium_threshold) for a given field."""
        high = self.config.field_thresholds.get(
            field_name,
            self.DEFAULT_FIELD_THRESHOLDS.get(field_name, self.config.default_high_threshold),
        )
        medium = self.config.default_medium_threshold
        return high, medium

    def evaluate_field(
        self,
        field_name: str,
        confidence: float,
        normalized_value: Any,
        raw_text: Optional[str] = None,
    ) -> ConfidenceEvaluationResult:
        """
        Deterministically evaluates extracted field confidence against configured policy.
        """
        high_thresh, med_thresh = self.get_thresholds(field_name)

        # 1. Missing or empty extraction
        if normalized_value is None:
            return ConfidenceEvaluationResult(
                field=field_name,
                confidence=float(confidence),
                level=ConfidenceLevel.LOW,
                action=ConfidenceAction.ASK_CLARIFICATION,
                reason="missing_or_unextractable_value",
                normalized_value=None,
            )

        # 2. Deterministic validation check
        is_valid, validation_err = self._validate_field_value(field_name, normalized_value)
        if not is_valid:
            return ConfidenceEvaluationResult(
                field=field_name,
                confidence=float(confidence),
                level=ConfidenceLevel.LOW,
                action=ConfidenceAction.REJECT,
                reason=f"deterministic_validation_failed: {validation_err}",
                normalized_value=normalized_value,
            )

        # 3. Confidence threshold evaluation
        if confidence >= high_thresh:
            return ConfidenceEvaluationResult(
                field=field_name,
                confidence=float(confidence),
                level=ConfidenceLevel.HIGH,
                action=ConfidenceAction.ACCEPT,
                reason="confidence_above_threshold_and_valid",
                normalized_value=normalized_value,
            )
        elif confidence >= med_thresh:
            return ConfidenceEvaluationResult(
                field=field_name,
                confidence=float(confidence),
                level=ConfidenceLevel.MEDIUM,
                action=ConfidenceAction.ASK_CONFIRMATION,
                reason="confidence_below_auto_accept_threshold",
                normalized_value=normalized_value,
            )
        else:
            return ConfidenceEvaluationResult(
                field=field_name,
                confidence=float(confidence),
                level=ConfidenceLevel.LOW,
                action=ConfidenceAction.ASK_CLARIFICATION,
                reason="confidence_below_medium_threshold",
                normalized_value=normalized_value,
            )

    def _validate_field_value(self, field_name: str, value: Any) -> Tuple[bool, Optional[str]]:
        """Applies deterministic domain validation rules."""
        if field_name in ("budget_max", "budget_min") and value is not None:
            try:
                num = float(value)
                if num <= 0:
                    return False, "budget must be greater than zero"
            except (ValueError, TypeError):
                return False, "budget must be a valid numeric amount"

        elif field_name == "occupants" and value is not None:
            try:
                num = int(value)
                if num <= 0:
                    return False, "occupants count must be greater than zero"
            except (ValueError, TypeError):
                return False, "occupants must be a valid integer"

        elif field_name == "lease_duration_months" and value is not None:
            try:
                num = int(value)
                if num <= 0:
                    return False, "lease duration must be greater than zero"
            except (ValueError, TypeError):
                return False, "lease duration must be a valid integer"

        elif field_name == "preferred_locations" and value is not None:
            if not isinstance(value, list) or len(value) == 0:
                return False, "locations must be a non-empty list"

        return True, None
