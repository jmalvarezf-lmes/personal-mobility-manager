"""
Domain value object: NotificationRecipient.

Thin wrapper around a channel-defined recipient payload used to address a
notification (e.g. {"chat_id": 123456789} for Telegram). Mirrors
SerProviderCredentials/SerProviderSession's role: a named, typed value
crosses the port boundary rather than a bare dict. The exact shape of
`data` is opaque here since it's entirely channel-specific.

Unlike SerProviderCredentials/SerProviderSession, this IS persisted
directly (see UserNotificationChannelConfigRepository) — but in cleartext,
not encrypted, since a channel identifier like a Telegram chat_id is not a
credential.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class NotificationRecipient:
    """Opaque, channel-defined recipient address for a notification."""

    data: dict[str, Any]
