"""
Unit tests for SendNotification use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.domain.entities.user_preferences import UserPreferences
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
        self.configs: dict[tuple[UUID, str], NotificationRecipient] = {}

    def add(self, user_id: UUID, channel: str, recipient: NotificationRecipient) -> None:
        self.configs[(user_id, channel)] = recipient

    def find(self, user_id: UUID, channel: str) -> NotificationRecipient | None:
        return self.configs.get((user_id, channel))

    def find_all_by_user_id(self, user_id: UUID) -> list[tuple[str, NotificationRecipient]]:
        return [(channel, recipient) for (uid, channel), recipient in self.configs.items() if uid == user_id]


class InMemoryUserPreferencesRepo:
    def __init__(self) -> None:
        self.preferences: dict[UUID, UserPreferences] = {}

    def set(self, user_id: UUID, preferred_notification_channel: str | None) -> None:
        self.preferences[user_id] = UserPreferences(
            user_id=user_id,
            default_ticket_duration_minutes=60,
            auto_create_ticket=False,
            preferred_notification_channel=preferred_notification_channel,
            notification_language=None,
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return self.preferences.get(user_id)


def test_sends_to_preferred_connected_channel_and_returns_true() -> None:
    user_id = uuid4()
    channel = FakeNotificationChannel()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    recipient = NotificationRecipient(data={"chat_id": 1})
    config_repo.add(user_id, "telegram", recipient)
    preferences_repo.set(user_id, "telegram")
    uc = SendNotification(channels={"telegram": channel}, config_repo=config_repo, preferences_repo=preferences_repo)

    result = uc.execute(user_id=user_id, message=NotificationMessage(text="hello"))

    assert result is True
    assert channel.send_calls == [(recipient, NotificationMessage(text="hello"))]


def test_no_preferred_channel_set_returns_false_without_raising() -> None:
    user_id = uuid4()
    channel = FakeNotificationChannel()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    preferences_repo.set(user_id, None)
    uc = SendNotification(channels={"telegram": channel}, config_repo=config_repo, preferences_repo=preferences_repo)

    result = uc.execute(user_id=user_id, message=NotificationMessage(text="hello"))

    assert result is False
    assert channel.send_calls == []


def test_missing_preferences_row_returns_false_without_raising() -> None:
    user_id = uuid4()
    channel = FakeNotificationChannel()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()  # no row for user_id
    uc = SendNotification(channels={"telegram": channel}, config_repo=config_repo, preferences_repo=preferences_repo)

    result = uc.execute(user_id=user_id, message=NotificationMessage(text="hello"))

    assert result is False


def test_stale_preferred_channel_returns_false_with_no_fallback() -> None:
    """Preference points at a channel with no stored config (e.g. disconnected) — no other channel is tried."""
    user_id = uuid4()
    telegram_channel = FakeNotificationChannel()
    other_channel = FakeNotificationChannel()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    # user has "other" configured but prefers "telegram", which has no config
    config_repo.add(user_id, "other", NotificationRecipient(data={"id": 1}))
    preferences_repo.set(user_id, "telegram")
    uc = SendNotification(
        channels={"telegram": telegram_channel, "other": other_channel},
        config_repo=config_repo,
        preferences_repo=preferences_repo,
    )

    result = uc.execute(user_id=user_id, message=NotificationMessage(text="hello"))

    assert result is False
    assert telegram_channel.send_calls == []
    assert other_channel.send_calls == []


def test_channel_send_failure_propagates() -> None:
    """Documented decision: a single channel's send failure raises rather than being swallowed."""
    user_id = uuid4()
    channel = FakeNotificationChannel(send_error=NotificationChannelApiError("boom"))
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    config_repo.add(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    preferences_repo.set(user_id, "telegram")
    uc = SendNotification(channels={"telegram": channel}, config_repo=config_repo, preferences_repo=preferences_repo)

    with pytest.raises(NotificationChannelApiError):
        uc.execute(user_id=user_id, message=NotificationMessage(text="hello"))
