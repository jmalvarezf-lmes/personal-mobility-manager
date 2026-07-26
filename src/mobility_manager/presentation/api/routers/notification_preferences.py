"""
Presentation: Notification type preferences API router.

Endpoints:
  GET /notifications/types — list the notification_types catalog
  GET /notifications/preferences — return the authenticated user's
    per-type preferences, merged with catalog fallback defaults
  PUT /notifications/preferences/{type_key} — replace one type's
    enabled/config for the authenticated user

See notification-type-preferences spec.md for the full requirement set.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request

from mobility_manager.config import get_default_notification_movement_threshold_meters
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.exceptions import InvalidNotificationConfigError
from mobility_manager.domain.value_objects.notification_config_schema import (
    validate_notification_config,
)
from mobility_manager.presentation.api.deps import get_current_user
from mobility_manager.presentation.api.schemas import (
    NotificationPreferenceResponse,
    NotificationTypeResponse,
    UpdateNotificationPreferenceRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notification-preferences"])

# Types whose enabled state is mutually exclusive with UserPreferences.auto_create_ticket
# (see the notification-type-preferences and user-preferences specs). Each
# maps to the auto_create_ticket value that locks it — i.e. attempting to
# enable it while auto_create_ticket already equals this value is rejected.
_LOCKED_WHEN_AUTO_CREATE_TICKET_IS: dict[str, bool] = {
    "ser_zone_ticket_required": True,
    "ser_ticket_created": False,
    "ser_ticket_creation_failed": False,
}


def _effective_config(config_schema: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    """
    Merge a stored `config` with the type's fallback defaults.

    Only `threshold_m` has a fallback today
    (DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS) — an absent
    `threshold_m` key resolves to it whenever the type's config_schema
    declares that field, regardless of `enabled` (see spec.md: "This applies
    regardless of enabled").
    """
    merged = dict(config)
    if "threshold_m" in config_schema and "threshold_m" not in merged:
        merged["threshold_m"] = get_default_notification_movement_threshold_meters()
    return merged


@router.get("/types", response_model=list[NotificationTypeResponse])
def list_notification_types(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[NotificationTypeResponse]:
    """Return every row in the notification_types catalog."""
    repo = request.app.state.notification_preferences_repo
    return [
        NotificationTypeResponse(key=t.key, label=t.label, config_schema=t.config_schema) for t in repo.list_types()
    ]


@router.get("/preferences", response_model=list[NotificationPreferenceResponse])
def get_notification_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> list[NotificationPreferenceResponse]:
    """
    Return the authenticated user's preference for every catalog type.

    Joins the catalog with the user's stored rows: a catalog type with no
    matching row (e.g. added after the user's last login, before their next
    login's ensure_defaults self-heals it) is treated as its opt-in default
    (enabled=false, config={}) rather than omitted. Each entry's `config` is
    merged with fallback defaults for any declared field the user hasn't
    explicitly set.
    """
    repo = request.app.state.notification_preferences_repo
    types = repo.list_types()
    preferences_by_key = {p.type_key: p for p in repo.find_by_user_id(current_user.id)}

    result = []
    for notification_type in types:
        preference = preferences_by_key.get(notification_type.key)
        enabled = preference.enabled if preference is not None else False
        config = preference.config if preference is not None else {}
        result.append(
            NotificationPreferenceResponse(
                type_key=notification_type.key,
                enabled=enabled,
                config=_effective_config(notification_type.config_schema, config),
            )
        )
    return result


@router.put("/preferences/{type_key}", response_model=NotificationPreferenceResponse)
def update_notification_preference(
    request: Request,
    type_key: str,
    body: UpdateNotificationPreferenceRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> NotificationPreferenceResponse:
    """
    Replace `enabled`/`config` for the authenticated user's (user_id,
    type_key) row.

    404 if `type_key` isn't in the notification_types catalog. 422 if
    `config` fails that type's config_schema validation. 422 (no row
    change) if `body.enabled` is true and `type_key` is currently locked by
    the caller's `auto_create_ticket` state — `ser_zone_ticket_required` is
    locked while `auto_create_ticket=true`; `ser_ticket_created` and
    `ser_ticket_creation_failed` are locked while `auto_create_ticket=false`.
    Disabling a locked type is always accepted regardless of lock state.
    The persisted (not fallback-merged) config is returned, matching what
    was requested.

    Logs the outcome on success (user id, type_key, enabled, config) as an
    audit trail for "I enabled it but got nothing" debugging.
    """
    repo = request.app.state.notification_preferences_repo
    types_by_key = {t.key: t for t in repo.list_types()}
    notification_type = types_by_key.get(type_key)
    if notification_type is None:
        raise HTTPException(status_code=404, detail=f"Unknown notification type '{type_key}'")

    try:
        validate_notification_config(notification_type.config_schema, body.config)
    except InvalidNotificationConfigError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    locked_at_auto_create_ticket = _LOCKED_WHEN_AUTO_CREATE_TICKET_IS.get(type_key)
    if body.enabled and locked_at_auto_create_ticket is not None:
        user_preferences_repo = request.app.state.user_preferences_repo
        preferences = user_preferences_repo.find_by_user_id(current_user.id)
        auto_create_ticket = preferences.auto_create_ticket if preferences is not None else False
        if auto_create_ticket is locked_at_auto_create_ticket:
            raise HTTPException(
                status_code=422,
                detail=f"'{type_key}' cannot be enabled while auto_create_ticket is {auto_create_ticket!s}.",
            )

    updated = repo.update(
        user_id=current_user.id,
        type_key=type_key,
        enabled=body.enabled,
        config=body.config,
    )
    logger.info(
        "Notification preference updated: user=%s type_key=%s enabled=%s config=%s",
        current_user.id,
        updated.type_key,
        updated.enabled,
        updated.config,
    )
    return NotificationPreferenceResponse(
        type_key=updated.type_key,
        enabled=updated.enabled,
        config=updated.config,
    )
