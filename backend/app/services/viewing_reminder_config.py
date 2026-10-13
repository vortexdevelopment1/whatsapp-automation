"""
Viewing Reminder Configuration - Module 5 Phase 6
Centralized configuration model for viewing reminders timing and policies.
"""
from typing import List
from pydantic import BaseModel, Field


class ViewingReminderConfig(BaseModel):
    tenant_reminders_enabled: bool = True
    agent_reminders_enabled: bool = True
    reminder_offsets_minutes: List[int] = Field(default_factory=lambda: [1440, 120])
    max_reminder_attempts: int = 3
    timezone_behavior: str = "Asia/Singapore"
    version: str = "1.0"
    active: bool = True


DEFAULT_VIEWING_REMINDER_CONFIG = ViewingReminderConfig()
