"""
Value object helper: notification config-schema validation.

Validates a notification type's `config` dict against its `config_schema`
(as stored on NotificationType.config_schema — see
notification-type-preferences spec). Reused by both the API layer
(PUT /notifications/preferences/{type_key} -> 422 on failure) and, in
principle, by any future notification type that grows its own config shape.

Only the field shape this change actually needs is supported today:

    {"threshold_m": {"type": "integer", "min": 1}}

i.e. an integer field with an inclusive minimum. Unknown/extra keys in
`config_schema` are ignored rather than rejected (forward-compatible with a
schema key this validator doesn't understand yet); an unknown/extra key in
`config` itself is also ignored, since config_schema is the source of truth
for what's validated, not an exhaustive allow-list.
"""

from typing import Any

from mobility_manager.domain.exceptions import InvalidNotificationConfigError


def validate_notification_config(config_schema: dict[str, Any], config: dict[str, Any]) -> None:
    """
    Validate `config` against `config_schema`.

    Raises:
        InvalidNotificationConfigError: if any field declared in
            `config_schema` is present in `config` but fails validation.
            A field declared in the schema but absent from `config` is
            valid — callers resolve a missing value via their own fallback
            (e.g. DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS).
    """
    for field_name, field_schema in config_schema.items():
        if field_name not in config:
            continue

        value = config[field_name]
        field_type = field_schema.get("type")

        if field_type == "integer":
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidNotificationConfigError(f"'{field_name}' must be an integer, got {value!r}")

            minimum = field_schema.get("min")
            if minimum is not None and value < minimum:
                raise InvalidNotificationConfigError(f"'{field_name}' must be >= {minimum}, got {value}")
