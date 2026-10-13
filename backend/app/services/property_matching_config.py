from typing import Optional
from pydantic import BaseModel, Field
from app.models.enums import UnknownDataPolicy


class PropertyMatchingConfig(BaseModel):
    """
    Centralized configurable policy for Phase 3 Property Candidate Hard Filtering.
    """
    config_version: str = "v1.0"
    filter_rule_version: str = "v1.0"

    # Property Type
    strict_property_type: bool = True

    # Budget & Pricing
    budget_tolerance_percent: float = Field(
        default=0.0,
        ge=0.0,
        le=50.0,
        description="Allowed % above tenant's budget_max (e.g. 5.0 allows price up to budget_max * 1.05)"
    )

    # Bedrooms
    minimum_bedroom_strict: bool = True
    allow_extra_bedrooms: bool = True  # Tenant requiring 2 BR can accept 3 BR

    # Location
    location_mode: str = Field(
        default="CITY_AREA",
        description="Mode for matching location: EXACT, CITY_AREA, POSTAL_ZONE, CONFIGURED_ALIAS"
    )

    # Move-in Date
    move_in_tolerance_days: int = Field(
        default=14,
        ge=0,
        le=90,
        description="Allowed number of days property can be available after tenant's desired move-in date"
    )

    # Lease Terms
    lease_duration_strict: bool = True

    # Furnishing
    strict_furnishing: bool = False  # If True, tenant requiring FURNISHED will reject UNFURNISHED

    # Unknown Data Policies
    allow_unknown_availability: UnknownDataPolicy = UnknownDataPolicy.ALLOW_FOR_LATER_VERIFICATION
    allow_unknown_lease: UnknownDataPolicy = UnknownDataPolicy.NEEDS_REVIEW
    allow_unknown_furnishing: UnknownDataPolicy = UnknownDataPolicy.ALLOW_FOR_LATER_VERIFICATION
    allow_unknown_price: UnknownDataPolicy = UnknownDataPolicy.FILTER_OUT

    # Inventory Limits
    max_initial_candidates: int = Field(
        default=250,
        ge=10,
        le=2000,
        description="Maximum candidates retrieved from database before in-memory rule filtering"
    )

    class Config:
        frozen = False


DEFAULT_MATCHING_CONFIG = PropertyMatchingConfig()
