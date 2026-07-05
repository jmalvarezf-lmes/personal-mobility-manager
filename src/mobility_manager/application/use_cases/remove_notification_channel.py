"""
Application use case: RemoveNotificationChannel.

Deletes a user's stored configuration for a notification channel. Unlike
DisconnectSerTicketProvider, no server-side revocation is attempted first —
there is no equivalent operation for a channel like Telegram, where the bot
has no API to invalidate a chat_id (see design.md decision 8).
"""

from uuid import UUID

from mobility_manager.domain.ports.user_notification_channel_config_repository import (
    UserNotificationChannelConfigRepository,
)


class RemoveNotificationChannel:
    """Remove a user's configuration for a notification channel."""

    def __init__(self, config_repo: UserNotificationChannelConfigRepository) -> None:
        self._config_repo = config_repo

    def execute(self, user_id: UUID, channel: str) -> None:
        """
        Delete the stored configuration for (user_id, channel).

        Idempotent — completes without raising even if nothing was configured.
        """
        self._config_repo.delete(user_id, channel)
