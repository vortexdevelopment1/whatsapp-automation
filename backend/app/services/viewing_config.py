"""
Viewing Coordination Centralized Configuration
"""
from typing import List


class ViewingConfirmationPolicy:
    require_tenant_confirmation: bool = True
    require_agent_confirmation: bool = True
    agent_offer_counts_as_preconfirmation: bool = False
    tenant_selection_counts_as_preconfirmation: bool = False
    confirmation_timeout_minutes: int = 1440
    slot_lock_timeout_minutes: int = 120
    auto_confirm_if_both_preconfirmed: bool = False
    version: str = "1.0.0"


class ViewingConfig:
    DEFAULT_VIEWING_DURATION_MINUTES: int = 30
    DEFAULT_SLOT_INTERVAL_MINUTES: int = 30
    MAX_CANDIDATE_SLOTS_PER_MATCH: int = 6
    DEFAULT_TIMEZONE: str = "Asia/Singapore"
    MAX_ACTIVE_VIEWINGS_PER_LEAD: int = 5
    MAX_RESCHEDULE_ATTEMPTS: int = 3
    SLOT_EXPIRY_HOURS: int = 48
    TENANT_SELECTION_TIMEOUT_HOURS: int = 24
    AGENT_CONFIRMATION_TIMEOUT_HOURS: int = 12
    REMINDER_SCHEDULE_HOURS_BEFORE: List[int] = [24, 2]
    ALLOW_OVERLAPPING_ACTIVE_VIEWINGS_ACROSS_PROPERTIES: bool = True
    CONFIRMATION_POLICY: ViewingConfirmationPolicy = ViewingConfirmationPolicy()

    @classmethod
    def get_default_duration_minutes(cls) -> int:
        return cls.DEFAULT_VIEWING_DURATION_MINUTES

    @classmethod
    def get_default_timezone(cls) -> str:
        return cls.DEFAULT_TIMEZONE

    @classmethod
    def get_max_active_viewings(cls) -> int:
        return cls.MAX_ACTIVE_VIEWINGS_PER_LEAD

    @classmethod
    def get_confirmation_policy(cls) -> ViewingConfirmationPolicy:
        return cls.CONFIRMATION_POLICY

