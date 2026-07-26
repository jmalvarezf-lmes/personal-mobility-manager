"""
Presentation: Preferences API router.

Endpoints:
  GET /preferences — return the authenticated user's preferences
  PUT /preferences — replace the authenticated user's preferences
"""

from zoneinfo import available_timezones

from fastapi import APIRouter, Depends, HTTPException, Request

from mobility_manager.application.notification_templates import SUPPORTED_LANGUAGES
from mobility_manager.domain.entities.user import User
from mobility_manager.presentation.api.deps import get_current_user
from mobility_manager.presentation.api.schemas import (
    UpdateUserPreferencesRequest,
    UserPreferencesResponse,
)

router = APIRouter(prefix="/preferences", tags=["preferences"])


@router.get("", response_model=UserPreferencesResponse)
def get_preferences(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserPreferencesResponse:
    """
    Return the authenticated user's preferences.

    The login flow guarantees a preferences row exists for every user by the
    time they can reach this endpoint, so a missing row is treated as an
    unexpected/assertion-level failure, not a 404.
    """
    preferences_repo = request.app.state.user_preferences_repo
    preferences = preferences_repo.find_by_user_id(current_user.id)
    assert preferences is not None, f"No preferences row found for user {current_user.id}"
    return UserPreferencesResponse(
        default_ticket_duration_minutes=preferences.default_ticket_duration_minutes,
        auto_create_ticket=preferences.auto_create_ticket,
        preferred_notification_channel=preferences.preferred_notification_channel,
        notification_language=preferences.notification_language,
        timezone=preferences.timezone,
    )


@router.put("", response_model=UserPreferencesResponse)
def update_preferences(
    request: Request,
    body: UpdateUserPreferencesRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserPreferencesResponse:
    """
    Replace all five fields of the authenticated user's preferences.

    A non-null preferred_notification_channel must correspond to a channel
    the current user has already connected (checked via
    UserNotificationChannelConfigRepository.find) — otherwise 422. A
    non-null notification_language must be one of
    notification_templates.SUPPORTED_LANGUAGES — otherwise 422. A non-null
    timezone must be a recognized IANA timezone identifier (checked via
    zoneinfo.available_timezones()) — otherwise 422. `null` is always
    allowed for any of these three fields, to let the user clear the
    preference.

    Enabling `auto_create_ticket` (false -> true) additionally requires the
    user to have at least one connected SER ticket provider
    (UserSerProviderConfigRepository.list_connected_providers) — otherwise
    422, and no values (including auto_create_ticket itself) are changed.

    When `auto_create_ticket` actually changes value as part of a
    successful update, the three related notification preferences are
    cascaded (see user-preferences spec.md's transition table): enabling it
    locks `ser_zone_ticket_required` off and turns the two new
    ser_ticket_created/ser_ticket_creation_failed types on; disabling it
    turns those two back off and leaves `ser_zone_ticket_required` as-is.
    Each cascaded write preserves that row's existing `config` — only
    `enabled` is forced (see design.md decision 3/4). The preferences row
    update and every cascaded write happen inside one atomic
    transaction via `update_with_notification_cascade` — a mid-operation
    failure rolls back all of it, not just some (post-implementation fix
    11.6).
    """
    if body.preferred_notification_channel is not None:
        config_repo = request.app.state.user_notification_channel_config_repo
        recipient = config_repo.find(current_user.id, body.preferred_notification_channel)
        if recipient is None:
            raise HTTPException(
                status_code=422,
                detail=f"Channel '{body.preferred_notification_channel}' is not connected",
            )

    if body.notification_language is not None and body.notification_language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=422,
            detail=f"Language '{body.notification_language}' is not supported",
        )

    if body.timezone is not None and body.timezone not in available_timezones():
        raise HTTPException(
            status_code=422,
            detail=f"Timezone '{body.timezone}' is not a recognized IANA timezone",
        )

    preferences_repo = request.app.state.user_preferences_repo
    current = preferences_repo.find_by_user_id(current_user.id)
    assert current is not None, f"No preferences row found for user {current_user.id}"

    if body.auto_create_ticket and not current.auto_create_ticket:
        provider_config_repo = request.app.state.user_ser_provider_config_repo
        if not provider_config_repo.list_connected_providers(current_user.id):
            raise HTTPException(
                status_code=422,
                detail={
                    "error_code": "ser_provider_not_connected",
                    "message": "Connect a SER ticket provider before enabling automatic ticket creation.",
                },
            )

    auto_create_ticket_changed = body.auto_create_ticket != current.auto_create_ticket
    notification_cascade = _resolve_notification_cascade(
        auto_create_ticket_changed=auto_create_ticket_changed,
        enabling=body.auto_create_ticket,
    )

    updated = preferences_repo.update_with_notification_cascade(
        user_id=current_user.id,
        default_ticket_duration_minutes=body.default_ticket_duration_minutes,
        auto_create_ticket=body.auto_create_ticket,
        preferred_notification_channel=body.preferred_notification_channel,
        notification_language=body.notification_language,
        timezone=body.timezone,
        notification_cascade=notification_cascade,
    )

    return UserPreferencesResponse(
        default_ticket_duration_minutes=updated.default_ticket_duration_minutes,
        auto_create_ticket=updated.auto_create_ticket,
        preferred_notification_channel=updated.preferred_notification_channel,
        notification_language=updated.notification_language,
        timezone=updated.timezone,
    )


def _resolve_notification_cascade(*, auto_create_ticket_changed: bool, enabling: bool) -> list[tuple[str, bool]]:
    """
    Resolve the auto_create_ticket transition's cascade to the three related
    notification preference rows (see user-preferences spec.md's transition
    table), for `update_with_notification_cascade`. Empty when the value
    didn't actually change.
    """
    if not auto_create_ticket_changed:
        return []
    if enabling:
        return [
            ("ser_zone_ticket_required", False),
            ("ser_ticket_created", True),
            ("ser_ticket_creation_failed", True),
        ]
    return [
        ("ser_ticket_created", False),
        ("ser_ticket_creation_failed", False),
    ]
