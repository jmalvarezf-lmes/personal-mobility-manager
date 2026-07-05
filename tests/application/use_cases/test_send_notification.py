"""
Unit tests for SendNotification use case.
"""

from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.domain.exceptions import NotificationChannelApiError
from mobility_manager.domain.ports.notification_channel import NotificationChannelPort
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)


class FakeNotificationChannel(NotificationChannelPort):
    def __init__(self, send_error: Exception | None = None) -> None:
        self.send_calls: list[tuple[NotificationRecipient, NotificationMessage]] = []
        self._send_error = send_error

    def send(self, recipient: NotificationRecipient, message: NotificationMessage) -> None:
        self.send_calls.append((recipient, message))
        if self._send_error is not None:
            raise self._send_error


class InMemoryUserNotificationChannelConfigRepo:
    def __init__(self) -> None:
        self.configs: dict[UUID, list[tuple[str, NotificationRecipient]]] = {}

    def add(self, user_id: UUID, channel: str, recipient: NotificationRecipient) -> None:
        self.configs.setdefault(user_id, []).append((channel, recipient))

    def find_all_by_user_id(self, user_id: UUID) -> list[tuple[str, NotificationRecipient]]:
        return self.configs.get(user_id, [])


def test_sends_to_configured_channel_and_returns_true() -> None:
    user_id = uuid4()
    channel = FakeNotificationChannel()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    recipient = NotificationRecipient(data={"chat_id": 1})
    config_repo.add(user_id, "telegram", recipient)
    uc = SendNotification(channels={"telegram": channel}, config_repo=config_repo)

    result = uc.execute(user_id=user_id, text="hello")

    assert result is True
    assert channel.send_calls == [(recipient, NotificationMessage(text="hello"))]


def test_no_configured_channels_returns_false_without_raising() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    uc = SendNotification(channels={}, config_repo=config_repo)

    result = uc.execute(user_id=user_id, text="hello")

    assert result is False


def test_channel_send_failure_propagates() -> None:
    """Documented decision: a single channel's send failure raises rather than being swallowed."""
    user_id = uuid4()
    channel = FakeNotificationChannel(send_error=NotificationChannelApiError("boom"))
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    config_repo.add(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    uc = SendNotification(channels={"telegram": channel}, config_repo=config_repo)

    with pytest.raises(NotificationChannelApiError):
        uc.execute(user_id=user_id, text="hello")
