"""
Infrastructure: TelegramNotificationChannel.

Implements NotificationChannelPort.send() against Telegram's Bot API
sendMessage endpoint using a synchronous httpx.Client — mirroring
ElParkingSerTicketProvider's sync-client style. There is no async
requirement here: NotificationChannelPort.send is a plain synchronous method.
"""

import httpx

from mobility_manager.config import get_telegram_bot_token
from mobility_manager.domain.exceptions import NotificationChannelApiError
from mobility_manager.domain.ports.notification_channel import NotificationChannelPort
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)

_TELEGRAM_API_BASE_URL = "https://api.telegram.org"
_SEND_TIMEOUT_SECONDS = 15.0


class TelegramNotificationChannel(NotificationChannelPort):
    """Notification channel backed by the Telegram Bot API."""

    def __init__(self) -> None:
        # Fails fast if TELEGRAM_BOT_TOKEN is unset — keeps this channel
        # self-contained and safe to construct directly (e.g. in tests).
        self._bot_token = get_telegram_bot_token()

    def send(self, recipient: NotificationRecipient, message: NotificationMessage) -> None:
        """
        Send `message.text` to `recipient.data["chat_id"]` via Telegram's sendMessage API.

        Raises:
            NotificationChannelApiError: Network error, timeout, or a
                non-2xx response — no raw httpx exception escapes.
        """
        chat_id = recipient.data["chat_id"]
        url = f"{_TELEGRAM_API_BASE_URL}/bot{self._bot_token}/sendMessage"
        body = {"chat_id": chat_id, "text": message.text}

        try:
            with httpx.Client(timeout=_SEND_TIMEOUT_SECONDS) as client:
                response = client.post(url, json=body)
        except httpx.HTTPError as exc:
            raise NotificationChannelApiError(f"Telegram sendMessage request failed: {exc}") from exc

        if not response.is_success:
            raise NotificationChannelApiError(
                f"Telegram sendMessage returned unexpected status {response.status_code}: {response.text[:200]}"
            )
