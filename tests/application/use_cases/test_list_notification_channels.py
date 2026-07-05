"""
Unit tests for ListNotificationChannels use case.
"""

from uuid import UUID, uuid4

from mobility_manager.application.use_cases.list_notification_channels import (
    ListNotificationChannels,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)


class InMemoryUserNotificationChannelConfigRepo:
    def __init__(self, configs: dict[UUID, list[tuple[str, NotificationRecipient]]] | None = None) -> None:
        self._configs = configs or {}

    def find_all_by_user_id(self, user_id: UUID) -> list[tuple[str, NotificationRecipient]]:
        return self._configs.get(user_id, [])


def test_reports_configured_channels() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo(
        {user_id: [("telegram", NotificationRecipient(data={"chat_id": 1}))]}
    )
    uc = ListNotificationChannels(config_repo=config_repo)

    assert uc.execute(user_id) == ["telegram"]


def test_reports_empty_list_when_no_channels_configured() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    uc = ListNotificationChannels(config_repo=config_repo)

    assert uc.execute(user_id) == []
