"""
Domain entity: UserPreferences.

Represents a user's per-account settings (ticket-creation defaults, preferred
notification channel, notification language, timezone).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class UserPreferences:
    """Core user preferences entity — 1:1 with a User."""

    user_id: UUID
    default_ticket_duration_minutes: int
    auto_create_ticket: bool
    preferred_notification_channel: str | None
    notification_language: str | None
    timezone: str | None
    updated_at: datetime
