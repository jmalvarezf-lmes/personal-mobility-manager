"""
Unit tests for RemoveNotificationChannel use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mobility_manager.application.use_cases.remove_notification_channel import (
    RemoveNotificationChannel,
)
from mobility_manager.domain.entities.user_preferences import UserPreferences
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


class InMemoryUserPreferencesRepo:
    def __init__(self) -> None:
        self.preferences: dict[UUID, UserPreferences] = {}
        self.set_preferred_calls: list[tuple[UUID, str | None]] = []

    def set(self, user_id: UUID, preferred_notification_channel: str | None) -> None:
        self.preferences[user_id] = UserPreferences(
            user_id=user_id,
            default_ticket_duration_minutes=60,
            auto_create_ticket=False,
            preferred_notification_channel=preferred_notification_channel,
            notification_language=None,
            timezone=None,
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return self.preferences.get(user_id)

    def set_preferred_notification_channel(self, user_id: UUID, channel: str | None) -> None:
        self.set_preferred_calls.append((user_id, channel))
        existing = self.preferences.get(user_id)
        if existing is not None:
            self.preferences[user_id] = UserPreferences(
                user_id=existing.user_id,
                default_ticket_duration_minutes=existing.default_ticket_duration_minutes,
                auto_create_ticket=existing.auto_create_ticket,
                preferred_notification_channel=channel,
                notification_language=existing.notification_language,
                timezone=existing.timezone,
                updated_at=existing.updated_at,
            )


def test_removes_an_existing_configured_channel() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    config_repo.add(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    preferences_repo.set(user_id, None)
    uc = RemoveNotificationChannel(config_repo=config_repo, preferences_repo=preferences_repo)

    uc.execute(user_id=user_id, channel="telegram")

    assert config_repo.configs.get((user_id, "telegram")) is None
    assert config_repo.delete_calls == [(user_id, "telegram")]


def test_removing_an_already_absent_channel_completes_without_raising() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    uc = RemoveNotificationChannel(config_repo=config_repo, preferences_repo=preferences_repo)

    uc.execute(user_id=user_id, channel="telegram")  # should not raise

    assert config_repo.delete_calls == [(user_id, "telegram")]


def test_removing_the_preferred_channel_clears_the_preference() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    config_repo.add(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    preferences_repo.set(user_id, "telegram")
    uc = RemoveNotificationChannel(config_repo=config_repo, preferences_repo=preferences_repo)

    uc.execute(user_id=user_id, channel="telegram")

    assert preferences_repo.set_preferred_calls == [(user_id, None)]
    assert preferences_repo.find_by_user_id(user_id).preferred_notification_channel is None


def test_removing_a_non_preferred_channel_leaves_the_preference_untouched() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserNotificationChannelConfigRepo()
    preferences_repo = InMemoryUserPreferencesRepo()
    config_repo.add(user_id, "telegram", NotificationRecipient(data={"chat_id": 1}))
    config_repo.add(user_id, "other", NotificationRecipient(data={"id": 1}))
    preferences_repo.set(user_id, "telegram")
    uc = RemoveNotificationChannel(config_repo=config_repo, preferences_repo=preferences_repo)

    uc.execute(user_id=user_id, channel="other")

    assert preferences_repo.set_preferred_calls == []
    assert preferences_repo.find_by_user_id(user_id).preferred_notification_channel == "telegram"
