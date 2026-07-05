"""
Application use case: SendNotification.

Sends a text message to every notification channel a user has configured.
No channel-preference logic — with only one possible channel (Telegram) so
far, there's nothing to choose between yet (see design.md decision 6).

Decision — single-channel send failure behaviour: a failure raises rather
than being swallowed or tracked per-channel. Unlike DisconnectSerTicketProvider
(where a soft-fail signal is meaningful because there's a local deletion that
must proceed regardless), there is no "the rest of the operation must still
happen" requirement here — if a configured channel can't deliver, the caller
needs to know immediately rather than getting a silent partial failure.
Should a second channel type land, this can be revisited into a
per-channel report; today it stays simple, per tasks.md 4.1's guidance.
"""

from uuid import UUID

from mobility_manager.domain.ports.notification_channel import NotificationChannelPort
from mobility_manager.domain.ports.user_notification_channel_config_repository import (
    UserNotificationChannelConfigRepository,
)
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)


class SendNotification:
    """Send a text notification to all of a user's configured channels."""

    def __init__(
        self,
        channels: dict[str, NotificationChannelPort],
        config_repo: UserNotificationChannelConfigRepository,
    ) -> None:
        self._channels = channels
        self._config_repo = config_repo

    def execute(self, user_id: UUID, text: str) -> bool:
        """
        Send `text` to every channel configured for `user_id`.

        Args:
            user_id: The user to notify.
            text: The message body.

        Returns:
            True if at least one channel is configured for `user_id` (and
            the send was attempted for each); False if none are configured.

        Raises:
            NotificationChannelApiError: If a configured channel's send call
                fails — see the module docstring for why this isn't swallowed.
            KeyError: If a configured channel name has no matching instance
                in `channels` (misconfiguration, not an expected runtime path).
        """
        configured = self._config_repo.find_all_by_user_id(user_id)
        if not configured:
            return False

        message = NotificationMessage(text=text)
        for channel_name, recipient in configured:
            channel = self._channels[channel_name]
            channel.send(recipient, message)

        return True
