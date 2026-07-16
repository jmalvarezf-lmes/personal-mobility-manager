"""
Domain entity: NotificationType.

Represents one row of the notification_types catalog — a kind of
notification the platform can send (e.g. "location_moved"), along with the
JSON schema describing its per-user configurable fields (e.g. threshold_m).
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NotificationType:
    """Core notification type entity — catalog data, not user-specific."""

    key: str
    label: str
    config_schema: dict[str, Any]
