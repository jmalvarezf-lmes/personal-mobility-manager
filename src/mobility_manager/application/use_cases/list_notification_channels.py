"""
Application use case: ListNotificationChannels.

Thin delegation to UserNotificationChannelConfigRepository.find_all_by_user_id,
reporting which notification channels a user currently has configured.
"""

from uuid import UUID

from mobility_manager.domain.ports.user_notification_channel_config_repository import (
    UserNotificationChannelConfigRepository,
)


class ListNotificationChannels:
    """Report which notification channels a user has configured."""

    def __init__(self, config_repo: UserNotificationChannelConfigRepository) -> None:
        self._config_repo = config_repo

    def execute(self, user_id: UUID) -> list[str]:
        """Return the channel names for which `user_id` has a stored configuration."""
        return [channel for channel, _recipient in self._config_repo.find_all_by_user_id(user_id)]
