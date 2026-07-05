"""
Unit tests for RemoveNotificationChannel use case.
"""

from uuid import UUID, uuid4

from mobility_manager.application.use_cases.remove_notification_channel import (
    RemoveNotificationChannel,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)


class InMemoryUserNotificationChannelConfigRepo:
    def __init__(self) -> None:
        self.configs: dict[tuple[UUID, str], NotificationRecipient] = {}
        self.delete_calls: list[tuple[UUID, str]] = []

    def add(self, user_id: UUID, channel: str, recipient: NotificationRecipient) -> None:
        self.configs[(user_id, channel)] = recipient

    def delete(self, user_id: UUID, channel: str) -> None:
        self.delete_calls.append((user_id, channel))
        self.configs.pop((user_id, channel), None)


def test_removes_an_existing_configured_channel() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    config_repo.add(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    uc = RemoveNotificationChannel(config_repo=config_repo)

    uc.execute(user_id=user_id, channel="telegram")

    assert config_repo.configs.get((user_id, "telegram")) is None
    assert config_repo.delete_calls == [(user_id, "telegram")]


def test_removing_an_already_absent_channel_completes_without_raising() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    uc = RemoveNotificationChannel(config_repo=config_repo)

    uc.execute(user_id=user_id, channel="telegram")  # should not raise

    assert config_repo.delete_calls == [(user_id, "telegram")]
