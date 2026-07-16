"""
Presentation: Notification channels API router.

Endpoints:
  POST /notifications/telegram/link-code — issue a signed, time-limited
    Telegram deep link for the current user (authenticated).
  POST /notifications/telegram/webhook — Telegram's inbound webhook (public,
    validated via the X-Telegram-Bot-Api-Secret-Token header instead of a
    user session, since Telegram — not an authenticated user — calls this).
  GET /notifications/channels — list the current user's configured
    notification channels (authenticated).
  DELETE /notifications/channels/{channel} — remove a configured channel
    (authenticated). No server-side revocation step exists to report on.
  GET /notifications/available-channels — list every channel registered in
    the running system, independent of what any user has configured
    (authenticated).
  GET /notifications/languages — list the system's supported notification
    languages (authenticated).
"""

import logging
import secrets
from typing import Any

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import Response

from mobility_manager.application.notification_templates import SUPPORTED_LANGUAGES, render
from mobility_manager.config import get_telegram_bot_username, get_telegram_webhook_secret
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.exceptions import NotificationChannelApiError
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)
from mobility_manager.infrastructure.telegram_link import verify_link_token
from mobility_manager.presentation.api.deps import get_current_user
from mobility_manager.presentation.api.schemas import (
    NotificationChannelsResponse,
    NotificationLanguagesResponse,
    TelegramLinkCodeResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])

_START_COMMAND_PREFIX = "/start "


@router.post("/telegram/link-code", response_model=TelegramLinkCodeResponse)
def create_telegram_link_code(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> TelegramLinkCodeResponse:
    """Issue a signed, time-limited Telegram deep link for the authenticated user."""
    use_case = request.app.state.generate_telegram_link_code

    token = use_case.execute(current_user.id)
    deep_link = f"https://t.me/{get_telegram_bot_username()}?start={token}"

    return TelegramLinkCodeResponse(deep_link=deep_link)


@router.post("/telegram/webhook")
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),  # noqa: B008
) -> dict[str, Any]:
    """
    Receive Telegram bot updates.

    Validates the webhook secret header before doing anything else. For a
    valid `/start <token>` message, verifies the token, stores the sender's
    chat_id as the token's user's Telegram recipient, and sends a
    confirmation message back to that chat.
    """
    if x_telegram_bot_api_secret_token is None or not secrets.compare_digest(
        x_telegram_bot_api_secret_token, get_telegram_webhook_secret()
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook secret token")

    update = await request.json()
    message = update.get("message") or {}
    text = message.get("text") or ""
    chat = message.get("chat") or {}
    chat_id = chat.get("id")

    if not text.startswith(_START_COMMAND_PREFIX) or chat_id is None:
        return {"ok": True}

    token = text[len(_START_COMMAND_PREFIX) :].strip()
    try:
        user_id = verify_link_token(token)
    except ValueError:
        logger.warning("Rejected Telegram link attempt with an invalid or expired token")
        return {"ok": True}

    config_repo = request.app.state.user_notification_channel_config_repo
    config_repo.save(user_id, "telegram", NotificationRecipient(data={"chat_id": chat_id}))

    # Auto-select "telegram" as the preferred channel if the user has no
    # preference yet (see design.md decision 4) — never overrides an
    # existing preference, so connecting a later channel doesn't silently
    # switch what's already chosen.
    preferences_repo = request.app.state.user_preferences_repo
    preferences = preferences_repo.find_by_user_id(user_id)
    if preferences is not None and preferences.preferred_notification_channel is None:
        preferences_repo.set_preferred_notification_channel(user_id, "telegram")

    language = preferences.notification_language if preferences is not None else None
    telegram_channel = request.app.state.notification_channels["telegram"]
    try:
        telegram_channel.send(
            NotificationRecipient(data={"chat_id": chat_id}),
            NotificationMessage(text=render("telegram_linked", language)),
        )
    except NotificationChannelApiError:
        logger.exception("Failed to send Telegram link confirmation message")

    return {"ok": True}


@router.get("/available-channels", response_model=NotificationChannelsResponse)
def list_available_channels(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> NotificationChannelsResponse:
    """
    List every notification channel registered in the running system.

    Sourced directly from app.state.notification_channels — the same dict
    built once in app.py's lifespan setup — so there's exactly one place a
    new channel gets registered (see design.md decision 1). Independent of
    what the current user has configured; that's GET /notifications/channels.
    """
    return NotificationChannelsResponse(channels=list(request.app.state.notification_channels.keys()))


@router.get("/languages", response_model=NotificationLanguagesResponse)
def list_languages(
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> NotificationLanguagesResponse:
    """
    List the system's supported notification languages.

    Sourced directly from notification_templates.SUPPORTED_LANGUAGES — the
    same single source of truth PUT /preferences' notification_language
    validation already uses (see design.md decision 6).
    """
    return NotificationLanguagesResponse(languages=sorted(SUPPORTED_LANGUAGES))


@router.get("/channels", response_model=NotificationChannelsResponse)
def list_channels(
    request: Request,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> NotificationChannelsResponse:
    """List the notification channels the authenticated user has configured."""
    use_case = request.app.state.list_notification_channels

    channels = use_case.execute(current_user.id)

    return NotificationChannelsResponse(channels=channels)


@router.delete("/channels/{channel}", status_code=204)
def delete_channel(
    request: Request,
    channel: str,
    current_user: User = Depends(get_current_user),  # noqa: B008
) -> Response:
    """
    Remove the authenticated user's configuration for `channel`.

    Returns 204 No Content — there is no server-side revocation step to
    report on, unlike the SER provider disconnect endpoint.
    """
    use_case = request.app.state.remove_notification_channel

    use_case.execute(user_id=current_user.id, channel=channel)

    return Response(status_code=204)
