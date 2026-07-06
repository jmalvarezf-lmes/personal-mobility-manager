"""
Application use case: SendNotification.

Delivers a pre-built NotificationMessage to a user's single preferred
notification channel only (see design.md decision 3). This replaces the
previous fan-out-to-every-configured-channel behaviour now that a preference
exists to disambiguate "which one" — deliberately fail-closed: if the
preference is unset, or set to a channel the user no longer has connected (a
stale preference), nothing is sent and no other configured channel is used
as a fallback. Reintroducing a fallback would reintroduce the same "which
one, and why" ambiguity the preference exists to remove (see design.md
decision 3's rejected alternative).

SendNotification does not build message text, look up templates, or resolve
language preferences itself — callers (e.g. NotificationDispatchHandler, the
Telegram webhook) construct the fully-formed, localized NotificationMessage
before calling execute(). This keeps SendNotification a pure "deliver to the
preferred channel" operation (see design.md decision 5).
"""

from uuid import UUID

from mobility_manager.domain.ports.notification_channel import NotificationChannelPort
from mobility_manager.domain.ports.user_notification_channel_config_repository import (
    UserNotificationChannelConfigRepository,
)
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)


class SendNotification:
    """Send a text notification to a user's preferred notification channel only."""

    def __init__(
        self,
        channels: dict[str, NotificationChannelPort],
        config_repo: UserNotificationChannelConfigRepository,
        preferences_repo: UserPreferencesRepository,
    ) -> None:
        self._channels = channels
        self._config_repo = config_repo
        self._preferences_repo = preferences_repo

    def execute(self, user_id: UUID, message: NotificationMessage) -> bool:
        """
        Send `message` via `user_id`'s preferred notification channel, if connected.

        Args:
            user_id: The user to notify.
            message: The fully-built, already-localized message to deliver.

        Returns:
            True if the preferred channel is set, a configuration exists for
            it, and the send was attempted. False without raising if no
            preference is set, or if it's set but stale (no configuration
            exists for that channel) — no fallback to any other configured
            channel in either case.

        Raises:
            NotificationChannelApiError: If the preferred channel's send
                call fails — not swallowed, so the caller knows immediately.
            KeyError: If the preferred channel name has no matching instance
                in `channels` (misconfiguration, not an expected runtime path).
        """
        preferences = self._preferences_repo.find_by_user_id(user_id)
        if preferences is None or preferences.preferred_notification_channel is None:
            return False

        preferred_channel = preferences.preferred_notification_channel
        recipient = self._config_repo.find(user_id, preferred_channel)
        if recipient is None:
            return False

        channel = self._channels[preferred_channel]
        channel.send(recipient, message)

        return True
