"""
Application use case: RemoveNotificationChannel.

Deletes a user's stored configuration for a notification channel. Unlike
DisconnectSerTicketProvider, no server-side revocation is attempted first —
there is no equivalent operation for a channel like Telegram, where the bot
has no API to invalidate a chat_id (see design.md decision 8).

Additionally clears the user's preferred_notification_channel when the
removed channel is the one currently preferred (see design.md decision 4) —
leaving a stale preference pointing at a now-disconnected channel would be
exactly the inconsistency SendNotification's fail-closed behaviour is meant
to guard against, so it's cleared eagerly here instead.
"""

from uuid import UUID

from mobility_manager.domain.ports.user_notification_channel_config_repository import (
    UserNotificationChannelConfigRepository,
)
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)


class RemoveNotificationChannel:
    """Remove a user's configuration for a notification channel."""

    def __init__(
        self,
        config_repo: UserNotificationChannelConfigRepository,
        preferences_repo: UserPreferencesRepository,
    ) -> None:
        self._config_repo = config_repo
        self._preferences_repo = preferences_repo

    def execute(self, user_id: UUID, channel: str) -> None:
        """
        Delete the stored configuration for (user_id, channel).

        Idempotent — completes without raising even if nothing was configured.
        If `channel` equals the user's current preferred_notification_channel,
        the preference is cleared to None in the same operation.
        """
        self._config_repo.delete(user_id, channel)

        preferences = self._preferences_repo.find_by_user_id(user_id)
        if preferences is not None and preferences.preferred_notification_channel == channel:
            self._preferences_repo.set_preferred_notification_channel(user_id, None)
