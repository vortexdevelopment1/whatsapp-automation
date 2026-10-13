from typing import Optional
from pydantic import BaseModel, Field, model_validator
from app.models.enums import MissingDataScoringPolicy


class PropertyScoringConfig(BaseModel):
    """
    Centralized configurable scoring weights, thresholds, and missing-data policies
    for Module 4 Phase 4 Property Scoring & Ranking.
    """
    scoring_config_version: str = "v1.0"
    active: bool = True

    # 1. Scoring Weights (Must sum to 100.0)
    location_weight: float = Field(
        default=30.0,
        ge=0.0,
        le=100.0,
        description="Weight for geographical/location match"
    )
    budget_weight: float = Field(
        default=25.0,
        ge=0.0,
        le=100.0,
        description="Weight for budget and rental price fit"
    )
    property_type_weight: float = Field(
        default=15.0,
        ge=0.0,
        le=100.0,
        description="Weight for property type compatibility"
    )
    bedrooms_weight: float = Field(
        default=10.0,
        ge=0.0,
        le=100.0,
        description="Weight for bedroom count fit"
    )
    move_in_weight: float = Field(
        default=8.0,
        ge=0.0,
        le=100.0,
        description="Weight for move-in availability date fit"
    )
    lease_weight: float = Field(
        default=5.0,
        ge=0.0,
        le=100.0,
        description="Weight for lease duration compatibility"
    )
    furnishing_weight: float = Field(
        default=4.0,
        ge=0.0,
        le=100.0,
        description="Weight for furnishing match"
    )
    availability_weight: float = Field(
        default=3.0,
        ge=0.0,
        le=100.0,
        description="Weight for listing availability verification status"
    )

    # 2. Thresholds and Caps
    minimum_score_for_outreach: float = Field(
        default=75.0,
        ge=0.0,
        le=100.0,
        description="Minimum score required to qualify candidate for agent outreach"
    )
    maximum_candidates_for_agent_verification: int = Field(
        default=10,
        ge=1,
        le=100,
        description="Maximum top-N candidates marked READY_FOR_AGENT_VERIFICATION"
    )

    # 3. Policy Configurations
    missing_data_policy: MissingDataScoringPolicy = Field(
        default=MissingDataScoringPolicy.NEUTRAL,
        description="Scoring handling for optional missing data (NEUTRAL, REDUCED, NO_SCORE, NEEDS_REVIEW)"
    )
    extra_bedroom_policy: str = Field(
        default="EQUAL",
        description="Policy for bedrooms > requested: 'EQUAL' (full score) or 'SLIGHT_PENALTY' (0.95)"
    )

    @model_validator(mode="after")
    def validate_weights_sum(self) -> "PropertyScoringConfig":
        total_weight = (
            self.location_weight
            + self.budget_weight
            + self.property_type_weight
            + self.bedrooms_weight
            + self.move_in_weight
            + self.lease_weight
            + self.furnishing_weight
            + self.availability_weight
        )
        if abs(total_weight - 100.0) > 0.05:
            raise ValueError(
                f"Scoring weights must sum to 100.0. Current sum: {total_weight:.2f}"
            )
        return self


DEFAULT_SCORING_CONFIG = PropertyScoringConfig()
