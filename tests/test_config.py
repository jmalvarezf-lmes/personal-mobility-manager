"""
Unit tests for mobility_manager.config helpers touched by
add-notification-type-preferences: the legacy env var warning and the
shared resolve_effective_threshold helper.
"""

import logging

import pytest

from mobility_manager.config import (
    get_default_notification_movement_threshold_meters,
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
