from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


class ShortlistConfig(BaseModel):
    minimum_shortlist_score: Decimal = Field(
        default=Decimal("70.0"),
        description="Minimum match score required for automatic shortlist eligibility",
    )
    max_shortlist_size: int = Field(
        default=5,
        description="Maximum number of candidates in a generated shortlist",
    )
    allow_conditional_candidates: bool = Field(
        default=True,
        description="Whether to include conditional candidates if verified count < max_shortlist_size",
    )
    require_agent_verified_availability: bool = Field(
        default=True,
        description="Whether agent-confirmed availability is strictly required for verified shortlist status",
    )
    require_current_score: bool = Field(
        default=True,
        description="Whether stale scores block final shortlist readiness until re-scored",
    )
    prefer_verified_over_conditional: bool = Field(
        default=True,
        description="Whether verified candidates always rank ahead of conditional candidates regardless of score",
    )
    shortlist_sorting_policy: str = Field(
        default="SCORE_DESC",
        description="Sorting policy within same qualification category ('SCORE_DESC', 'PRICE_ASC')",
    )
    max_move_in_delay_days_conditional: int = Field(
        default=14,
        description="Max days after preferred move-in date allowed for conditional candidacy",
    )
    max_budget_tolerance_percentage_conditional: Decimal = Field(
        default=Decimal("10.0"),
        description="Max budget overrun percentage allowed for conditional candidacy",
    )
    active: bool = True
    version: str = "1.0.0"
