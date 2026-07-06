"""
Presentation: Preferences API router.

Endpoints:
  GET /preferences — return the authenticated user's preferences
  PUT /preferences — replace the authenticated user's preferences
"""

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
    )


@router.put("", response_model=UserPreferencesResponse)
def update_preferences(
    request: Request,
    body: UpdateUserPreferencesRequest,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> UserPreferencesResponse:
    """
    Replace all four fields of the authenticated user's preferences.

    A non-null preferred_notification_channel must correspond to a channel
    the current user has already connected (checked via
    UserNotificationChannelConfigRepository.find) — otherwise 422. A
    non-null notification_language must be one of
    notification_templates.SUPPORTED_LANGUAGES — otherwise 422. `null` is
    always allowed for either field, to let the user clear the preference.
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

    preferences_repo = request.app.state.user_preferences_repo
    updated = preferences_repo.update(
        user_id=current_user.id,
        default_ticket_duration_minutes=body.default_ticket_duration_minutes,
        auto_create_ticket=body.auto_create_ticket,
        preferred_notification_channel=body.preferred_notification_channel,
        notification_language=body.notification_language,
    )
    return UserPreferencesResponse(
        default_ticket_duration_minutes=updated.default_ticket_duration_minutes,
        auto_create_ticket=updated.auto_create_ticket,
        preferred_notification_channel=updated.preferred_notification_channel,
        notification_language=updated.notification_language,
    )
