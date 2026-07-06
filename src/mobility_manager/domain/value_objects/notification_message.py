"""
Domain value object: NotificationMessage.

Wraps the content of a notification to be delivered via a
NotificationChannelPort: `text` for every channel (Telegram, and eventually
WhatsApp), plus an optional `location`, since the vehicle-moved notification
needs to carry a map pin alongside its text. `location` is channel-agnostic
in shape even though only TelegramNotificationChannel has a concrete
`sendLocation` implementation so far (see design.md decision 4).
"""

from dataclasses import dataclass

from mobility_manager.domain.value_objects.location import GeoLocation


@dataclass(frozen=True)
class NotificationMessage:
    """Text content of a notification, with an optional location."""

    text: str
    location: GeoLocation | None = None
