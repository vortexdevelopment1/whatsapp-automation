from typing import Optional
from pydantic import BaseModel, Field


class AgentFollowUpConfig(BaseModel):
    """
    Centralized configurable follow-up SLA durations, attempt limits,
    contact limits, and fallback behavior for Module 4 Phase 7.
    """
    version: str = "v1.0"
    active: bool = True

    # 1. SLA Timing Configuration (Minutes)
    initial_response_sla_minutes: int = Field(
        default=180,
        ge=1,
        description="Wait time in minutes before first agent follow-up is due"
    )
    followup_delay_minutes: int = Field(
        default=240,
        ge=1,
        description="Delay in minutes between consecutive follow-up nudges"
    )

    # 2. Attempt Limits
    max_followup_attempts: int = Field(
        default=2,
        ge=1,
        le=5,
        description="Maximum automated follow-up messages per outreach (e.g., attempt 1, attempt 2)"
    )

    # 3. Fallback Strategies
    alternate_listing_enabled: bool = Field(
        default=True,
        description="Try other active listings for the same canonical property when agent is unresponsive"
    )
    alternate_property_enabled: bool = Field(
        default=True,
        description="Try next ranked candidate property when no alternate listing exists"
    )
    min_score_for_alternate_property: float = Field(
        default=70.0,
        ge=0.0,
        le=100.0,
        description="Minimum match score required to automatically verify next ranked property"
    )

    # 4. Global Contact Protections
    max_total_agent_contacts: int = Field(
        default=5,
        ge=1,
        description="Maximum total agent contacts allowed for a single lead before human review"
    )
    human_review_after_exhaustion: bool = Field(
        default=True,
        description="Escalate to human operator review when all fallback options are exhausted"
    )


DEFAULT_AGENT_FOLLOWUP_CONFIG = AgentFollowUpConfig()
