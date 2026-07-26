"""
Unit tests for mobility_manager.config helpers touched by
add-notification-type-preferences: the legacy env var warning and the
shared resolve_effective_threshold helper.
"""

import logging

import pytest

from mobility_manager.config import (
    get_ambient_label_poll_interval_minutes,
    get_ambient_label_request_delay_seconds,
    get_ambient_label_retry_cooldown_hours,
    get_default_notification_movement_threshold_meters,
    get_event_publisher_max_workers,
    get_session_cleanup_retention_days,
    resolve_effective_threshold,
)


def test_no_warning_when_new_env_var_is_set(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "75")
    monkeypatch.delenv("NOTIFICATION_MOVEMENT_THRESHOLD_METERS", raising=False)

    with caplog.at_level(logging.WARNING):
        result = get_default_notification_movement_threshold_meters()

    assert result == 75.0
    assert caplog.records == []


def test_no_warning_when_neither_env_var_is_set(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.delenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", raising=False)
    monkeypatch.delenv("NOTIFICATION_MOVEMENT_THRESHOLD_METERS", raising=False)

    with caplog.at_level(logging.WARNING):
        result = get_default_notification_movement_threshold_meters()

    assert result == 50.0
    assert caplog.records == []


def test_warns_when_only_legacy_env_var_is_set(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "200")
    monkeypatch.delenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", raising=False)

    with caplog.at_level(logging.WARNING):
        result = get_default_notification_movement_threshold_meters()

    # Falls back to the 50 default — the legacy var is never read for its value.
    assert result == 50.0
    assert len(caplog.records) == 1
    assert "NOTIFICATION_MOVEMENT_THRESHOLD_METERS" in caplog.records[0].message
    assert "DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS" in caplog.records[0].message


def test_no_warning_when_both_env_vars_are_set(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "200")
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "75")

    with caplog.at_level(logging.WARNING):
        result = get_default_notification_movement_threshold_meters()

    assert result == 75.0
    assert caplog.records == []


def test_resolve_effective_threshold_uses_config_value_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    assert resolve_effective_threshold({"threshold_m": 20}) == 20.0


def test_resolve_effective_threshold_falls_back_to_env_default_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
    assert resolve_effective_threshold({}) == 50.0


class TestEventPublisherConfig:
    def test_max_workers_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("EVENT_PUBLISHER_MAX_WORKERS", raising=False)
        assert get_event_publisher_max_workers() == 4

    def test_max_workers_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EVENT_PUBLISHER_MAX_WORKERS", "8")
        assert get_event_publisher_max_workers() == 8

    def test_max_workers_falls_back_on_parse_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("EVENT_PUBLISHER_MAX_WORKERS", "not-a-number")
        assert get_event_publisher_max_workers() == 4


class TestAmbientLabelConfig:
    def test_poll_interval_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AMBIENT_LABEL_POLL_INTERVAL_MINUTES", raising=False)
        assert get_ambient_label_poll_interval_minutes() == 60

    def test_poll_interval_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AMBIENT_LABEL_POLL_INTERVAL_MINUTES", "15")
        assert get_ambient_label_poll_interval_minutes() == 15

    def test_poll_interval_falls_back_on_parse_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AMBIENT_LABEL_POLL_INTERVAL_MINUTES", "not-a-number")
        assert get_ambient_label_poll_interval_minutes() == 60

    def test_retry_cooldown_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AMBIENT_LABEL_RETRY_COOLDOWN_HOURS", raising=False)
        assert get_ambient_label_retry_cooldown_hours() == 24

    def test_retry_cooldown_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AMBIENT_LABEL_RETRY_COOLDOWN_HOURS", "6")
        assert get_ambient_label_retry_cooldown_hours() == 6

    def test_retry_cooldown_falls_back_on_parse_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AMBIENT_LABEL_RETRY_COOLDOWN_HOURS", "not-a-number")
        assert get_ambient_label_retry_cooldown_hours() == 24

    def test_request_delay_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("AMBIENT_LABEL_REQUEST_DELAY_SECONDS", raising=False)
        assert get_ambient_label_request_delay_seconds() == 5

    def test_request_delay_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AMBIENT_LABEL_REQUEST_DELAY_SECONDS", "1")
        assert get_ambient_label_request_delay_seconds() == 1

    def test_request_delay_falls_back_on_parse_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AMBIENT_LABEL_REQUEST_DELAY_SECONDS", "not-a-number")
        assert get_ambient_label_request_delay_seconds() == 5


class TestSessionCleanupRetentionDays:
    def test_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SESSION_CLEANUP_RETENTION_DAYS", raising=False)
        assert get_session_cleanup_retention_days() == 30

    def test_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SESSION_CLEANUP_RETENTION_DAYS", "7")
        assert get_session_cleanup_retention_days() == 7

    def test_falls_back_on_parse_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SESSION_CLEANUP_RETENTION_DAYS", "not-a-number")
        assert get_session_cleanup_retention_days() == 30

    def test_negative_value_falls_back_to_default_and_warns(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        4R review fix 2: a negative retention window would push
        CleanupExpiredSessions's cutoff into the future and delete every
        active session — must fall back to the 30-day default instead.
        """
        monkeypatch.setenv("SESSION_CLEANUP_RETENTION_DAYS", "-5")

        with caplog.at_level(logging.WARNING):
            result = get_session_cleanup_retention_days()

        assert result == 30
        assert len(caplog.records) == 1
        assert "SESSION_CLEANUP_RETENTION_DAYS" in caplog.records[0].message
