"""
Domain value object: NotificationMessage.

Wraps the text of a notification to be delivered via a
NotificationChannelPort. Deliberately just `text: str` — every channel
planned so far (Telegram, and eventually WhatsApp) supports plain text
messages; richer message types (buttons, images) can be added if a real
future need appears, not speculatively now.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class NotificationMessage:
    """Plain-text content of a notification."""

    text: str
