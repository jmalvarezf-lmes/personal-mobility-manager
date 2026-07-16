"""
Domain entity: UserNotificationPreference.

Represents a single (user_id, type_key) row of user_notification_preferences
— whether a user has a given notification type enabled, and its per-type
configuration (e.g. {"threshold_m": 20}). 1:many with a User (one row per
catalog notification type), unlike UserPreferences which is 1:1.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class UserNotificationPreference:
    """Core user notification preference entity — one row per (user, type)."""

    user_id: UUID
    type_key: str
    enabled: bool
    config: dict[str, Any]
    updated_at: datetime
