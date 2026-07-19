"""
Unit tests for validate_notification_config.

Covers the happy path (valid value, absent field), the wrong-type rejection,
the bool-vs-integer guard (Python bools are `int` subclasses, so `True`/
`False` must be rejected for an `integer`-typed field), and the exact
boundary case (`value == min` is valid, `value == min - 1` is invalid).
"""

import pytest

from mobility_manager.domain.exceptions import InvalidNotificationConfigError
from mobility_manager.domain.value_objects.notification_config_schema import (
    validate_notification_config,
)

_THRESHOLD_SCHEMA = {"threshold_m": {"type": "integer", "min": 1}}


def test_valid_integer_value_passes() -> None:
    validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": 20})


def test_field_absent_from_config_passes() -> None:
    """A field declared in the schema but absent from config is valid — the caller resolves its own fallback."""
    validate_notification_config(_THRESHOLD_SCHEMA, {})


def test_unknown_extra_config_key_is_rejected() -> None:
    """
    `config` may not carry a key absent from `config_schema` — reversal of
    the prior "ignore extra keys" behavior (see design.md decision 7).
    """
    with pytest.raises(InvalidNotificationConfigError, match="unrelated"):
        validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": 20, "unrelated": "value"})


def test_unknown_key_alone_is_rejected_even_when_no_declared_field_is_present() -> None:
    with pytest.raises(InvalidNotificationConfigError, match="unrelated"):
        validate_notification_config(_THRESHOLD_SCHEMA, {"unrelated": "value"})


def test_unknown_extra_schema_key_is_ignored() -> None:
    schema = {"threshold_m": {"type": "integer", "min": 1}, "future_field": {"type": "string"}}
    validate_notification_config(schema, {"threshold_m": 20})


def test_non_integer_value_raises() -> None:
    with pytest.raises(InvalidNotificationConfigError, match="must be an integer"):
        validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": "not-a-number"})


def test_float_value_raises() -> None:
    with pytest.raises(InvalidNotificationConfigError, match="must be an integer"):
        validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": 20.5})


@pytest.mark.parametrize("value", [True, False])
def test_bool_value_raises_even_though_bool_is_an_int_subclass(value: bool) -> None:
    """Python bools are `int` subclasses, so `isinstance(True, int)` is True — must be explicitly rejected."""
    with pytest.raises(InvalidNotificationConfigError, match="must be an integer"):
        validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": value})


def test_value_equal_to_min_is_valid() -> None:
    validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": 1})


def test_value_one_below_min_raises() -> None:
    with pytest.raises(InvalidNotificationConfigError, match="must be >= 1"):
        validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": 0})


def test_negative_value_raises() -> None:
    with pytest.raises(InvalidNotificationConfigError, match="must be >= 1"):
        validate_notification_config(_THRESHOLD_SCHEMA, {"threshold_m": -5})
