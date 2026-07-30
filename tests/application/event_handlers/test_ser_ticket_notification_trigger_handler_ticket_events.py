"""
Unit tests for SerTicketNotificationTriggerHandler.on_ticket_created and
on_ticket_creation_failed.

Covers the ser-ticket-auto-creation spec's notification scenarios: enabled
preference triggers the notification, disabled/missing preference skips
silently, message localization, dates formatted in the owner's configured
timezone (falling back to UTC when unset), and — for the failure path —
that `event.reason` never leaks into the rendered message or the
SendNotification.execute call args.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from mobility_manager.application.event_handlers.ser_ticket_notification_trigger_handler import (
    SerTicketNotificationTriggerHandler,
)
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.domain.events.ser_ticket_created import SerTicketCreated
from mobility_manager.domain.events.ser_ticket_creation_failed import (
    SerTicketCreationFailed,
)
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)

_CREATED_TYPE_KEY = "ser_ticket_created"
_CREATION_FAILED_TYPE_KEY = "ser_ticket_creation_failed"


class _FakeUserPreferencesRepo:
    def __init__(self) -> None:
        self.preferences: dict[UUID, UserPreferences] = {}

    def set(
        self,
        user_id: UUID,
        notification_language: str | None = None,
        timezone: str | None = None,
    ) -> None:
        self.preferences[user_id] = UserPreferences(
            user_id=user_id,
            default_ticket_duration_minutes=60,
            auto_create_ticket=True,
            preferred_notification_channel="telegram",
            notification_language=notification_language,
            timezone=timezone,
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id(self, user_id: UUID) -> UserPreferences | None:
        return self.preferences.get(user_id)


class _FakeNotificationPreferencesRepo:
    def __init__(self) -> None:
        self._rows: dict[tuple[UUID, str], UserNotificationPreference] = {}

    def set(self, user_id: UUID, type_key: str, enabled: bool, config: dict[str, Any] | None = None) -> None:
        self._rows[(user_id, type_key)] = UserNotificationPreference(
            user_id=user_id,
            type_key=type_key,
            enabled=enabled,
            config=config or {},
            updated_at=datetime.now(UTC),
        )

    def find_by_user_id_and_type(self, user_id: UUID, type_key: str) -> UserNotificationPreference | None:
        return self._rows.get((user_id, type_key))


class _FakeSendNotification:
    def __init__(self) -> None:
        self.calls: list[tuple[UUID, NotificationMessage]] = []

    def execute(self, user_id: UUID, message: NotificationMessage) -> bool:
        self.calls.append((user_id, message))
        return True


def _make_handler(
    preferences_repo: _FakeUserPreferencesRepo,
    notification_preferences_repo: _FakeNotificationPreferencesRepo,
    send_notification: _FakeSendNotification,
) -> SerTicketNotificationTriggerHandler:
    return SerTicketNotificationTriggerHandler(
        vehicle_repo=None,  # type: ignore[arg-type] - not exercised by these methods
        user_preferences_repo=preferences_repo,  # type: ignore[arg-type]
        notification_preferences_repo=notification_preferences_repo,  # type: ignore[arg-type]
        determine_ser_ticket_requirement=None,  # type: ignore[arg-type]
        ser_zone_recheck_gate=None,  # type: ignore[arg-type]
        send_notification=send_notification,  # type: ignore[arg-type]
    )


def _make_created_event(user_id: UUID) -> SerTicketCreated:
    return SerTicketCreated(
        vehicle_id=uuid4(),
        user_id=user_id,
        zone_number="163",
        start_date=datetime(2026, 7, 26, 10, 0, tzinfo=UTC),
        end_date=datetime(2026, 7, 26, 12, 0, tzinfo=UTC),
    )


def _make_creation_failed_event(user_id: UUID, reason: str = "provider_error") -> SerTicketCreationFailed:
    return SerTicketCreationFailed(
        vehicle_id=uuid4(),
        user_id=user_id,
        zone_number="163",
        reason=reason,
    )


class TestOnTicketCreated:
    def test_enabled_preference_sends_notification_with_both_dates(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATED_TYPE_KEY, enabled=True)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_created(_make_created_event(user_id))

        assert len(send_notification.calls) == 1
        called_user_id, message = send_notification.calls[0]
        assert called_user_id == user_id
        assert "163" in message.text

    def test_disabled_preference_skips(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATED_TYPE_KEY, enabled=False)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_created(_make_created_event(user_id))

        assert send_notification.calls == []

    def test_missing_preference_row_skips(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()  # no row
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_created(_make_created_event(user_id))

        assert send_notification.calls == []

    def test_message_localized_to_owner_language(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id, notification_language="es")
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATED_TYPE_KEY, enabled=True)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_created(_make_created_event(user_id))

        _, message = send_notification.calls[0]
        assert "automáticamente" in message.text

    def test_dates_formatted_in_owner_timezone(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id, timezone="Europe/Madrid")
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATED_TYPE_KEY, enabled=True)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_created(_make_created_event(user_id))

        _, message = send_notification.calls[0]
        # 2026-07-26 10:00 UTC / 12:00 UTC -> 12:00 / 14:00 CEST in Madrid.
        assert "12:00" in message.text
        assert "14:00" in message.text
        assert "10:00" not in message.text

    def test_dates_fall_back_to_utc_when_no_timezone_set(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id, timezone=None)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATED_TYPE_KEY, enabled=True)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_created(_make_created_event(user_id))

        _, message = send_notification.calls[0]
        assert "10:00" in message.text
        assert "12:00" in message.text

    def test_collaborator_failure_is_swallowed_and_never_raises(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATED_TYPE_KEY, enabled=True)

        class _RaisingSendNotification:
            def execute(self, user_id, message):
                raise RuntimeError("boom")

        handler = _make_handler(preferences_repo, notification_preferences_repo, _RaisingSendNotification())

        result = handler.on_ticket_created(_make_created_event(user_id))  # must not raise

        assert result is None


class TestOnTicketCreationFailed:
    def test_enabled_preference_sends_generic_notification(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATION_FAILED_TYPE_KEY, enabled=True)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_creation_failed(_make_creation_failed_event(user_id, reason="provider_error"))

        assert len(send_notification.calls) == 1
        called_user_id, message = send_notification.calls[0]
        assert called_user_id == user_id
        assert "163" in message.text
        assert "provider_error" not in message.text

    def test_disabled_preference_skips(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATION_FAILED_TYPE_KEY, enabled=False)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_creation_failed(_make_creation_failed_event(user_id))

        assert send_notification.calls == []

    def test_missing_preference_row_skips(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()  # no row
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_creation_failed(_make_creation_failed_event(user_id))

        assert send_notification.calls == []

    def test_reason_never_appears_in_message_regardless_of_value(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATION_FAILED_TYPE_KEY, enabled=True)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        for reason in (
            "no_provider_session",
            "vehicle_not_matched",
            "zone_not_found",
            "provider_error",
            "ticket_created_but_not_recorded",
        ):
            send_notification.calls.clear()
            handler.on_ticket_creation_failed(_make_creation_failed_event(user_id, reason=reason))
            _, message = send_notification.calls[0]
            assert reason not in message.text

    def test_ticket_created_but_not_recorded_reason_renders_distinct_possibly_created_message(self) -> None:
        """Only this one reason must flip the template's `possibly_created` branch."""
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATION_FAILED_TYPE_KEY, enabled=True)
        send_notification = _FakeSendNotification()
        handler = _make_handler(preferences_repo, notification_preferences_repo, send_notification)

        handler.on_ticket_creation_failed(_make_creation_failed_event(user_id, reason="provider_error"))
        _, generic_message = send_notification.calls[0]

        send_notification.calls.clear()
        handler.on_ticket_creation_failed(
            _make_creation_failed_event(user_id, reason="ticket_created_but_not_recorded")
        )
        _, possibly_created_message = send_notification.calls[0]

        assert generic_message.text != possibly_created_message.text
        assert "163" in possibly_created_message.text

    def test_collaborator_failure_is_swallowed_and_never_raises(self) -> None:
        user_id = uuid4()
        preferences_repo = _FakeUserPreferencesRepo()
        preferences_repo.set(user_id)
        notification_preferences_repo = _FakeNotificationPreferencesRepo()
        notification_preferences_repo.set(user_id, _CREATION_FAILED_TYPE_KEY, enabled=True)

        class _RaisingSendNotification:
            def execute(self, user_id, message):
                raise RuntimeError("boom")

        handler = _make_handler(preferences_repo, notification_preferences_repo, _RaisingSendNotification())

        result = handler.on_ticket_creation_failed(_make_creation_failed_event(user_id))  # must not raise

        assert result is None
