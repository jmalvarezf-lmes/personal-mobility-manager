"""
Presentation tests for the notification channels API endpoints.

POST /notifications/telegram/link-code
POST /notifications/telegram/webhook
GET /notifications/channels
DELETE /notifications/channels/{channel}
GET /notifications/available-channels
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.user_preferences import UserPreferences
from mobility_manager.infrastructure.telegram_link import generate_link_token
from mobility_manager.presentation.api.routers.notifications import router

_JWT_SECRET = "test-secret-for-notifications"
_WEBHOOK_SECRET = "test-webhook-secret"
_BOT_USERNAME = "TestMobilityBot"
_OWNER_ID = uuid4()


def _make_test_user(user_id: UUID | None = None) -> User:
    return User(
        id=user_id or _OWNER_ID,
        google_sub="sub123",
        email="owner@example.com",
        display_name="Owner",
        created_at=datetime.now(UTC),
    )


def _make_session_cookie(user: User, secret: str = _JWT_SECRET) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_preferences(
    user_id: UUID,
    preferred_notification_channel: str | None = None,
    notification_language: str | None = None,
) -> UserPreferences:
    return UserPreferences(
        user_id=user_id,
        default_ticket_duration_minutes=60,
        auto_create_ticket=False,
        preferred_notification_channel=preferred_notification_channel,
        notification_language=notification_language,
        updated_at=datetime.now(UTC),
    )


def _build_app(
    generate_link_code_uc=None,
    list_channels_uc=None,
    remove_channel_uc=None,
    user_repo=None,
    config_repo=None,
    notification_channels=None,
    preferences_repo=None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if generate_link_code_uc is not None:
        app.state.generate_telegram_link_code = generate_link_code_uc
    if list_channels_uc is not None:
        app.state.list_notification_channels = list_channels_uc
    if remove_channel_uc is not None:
        app.state.remove_notification_channel = remove_channel_uc
    if user_repo is not None:
        app.state.user_repo = user_repo
    if config_repo is not None:
        app.state.user_notification_channel_config_repo = config_repo
    if notification_channels is not None:
        app.state.notification_channels = notification_channels
    if preferences_repo is not None:
        app.state.user_preferences_repo = preferences_repo
    return app


def _build_authed_app(**kwargs) -> tuple[FastAPI, str]:
    user = _make_test_user()
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_id.return_value = user
    kwargs.setdefault("user_repo", mock_user_repo)
    app = _build_app(**kwargs)
    cookie = _make_session_cookie(user)
    return app, cookie


@pytest.fixture(autouse=True)
def _env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    monkeypatch.setenv("TELEGRAM_WEBHOOK_SECRET", _WEBHOOK_SECRET)
    monkeypatch.setenv("TELEGRAM_BOT_USERNAME", _BOT_USERNAME)


# ---------------------------------------------------------------------------
# POST /notifications/telegram/link-code
# ---------------------------------------------------------------------------


def test_link_code_unauthenticated_returns_401_without_contacting_use_case() -> None:
    mock_uc = MagicMock()
    mock_repo = MagicMock()
    mock_repo.find_by_id.return_value = None
    client = TestClient(_build_app(generate_link_code_uc=mock_uc, user_repo=mock_repo), raise_server_exceptions=False)

    response = client.post("/notifications/telegram/link-code")

    assert response.status_code == 401
    mock_uc.execute.assert_not_called()


def test_link_code_authenticated_returns_deep_link_with_token() -> None:
    mock_uc = MagicMock()
    mock_uc.execute.return_value = "signed-token-value"
    app, cookie = _build_authed_app(generate_link_code_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/notifications/telegram/link-code", cookies={"session": cookie})

    assert response.status_code == 200
    body = response.json()
    assert body["deep_link"] == f"https://t.me/{_BOT_USERNAME}?start=signed-token-value"
    mock_uc.execute.assert_called_once_with(_OWNER_ID)


# ---------------------------------------------------------------------------
# POST /notifications/telegram/webhook
# ---------------------------------------------------------------------------


def test_webhook_missing_secret_header_rejected_without_linking() -> None:
    mock_config_repo = MagicMock()
    app = _build_app(config_repo=mock_config_repo)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/notifications/telegram/webhook",
        json={"message": {"text": "/start abc", "chat": {"id": 1}}},
    )

    assert response.status_code == 401
    mock_config_repo.save.assert_not_called()


def test_webhook_incorrect_secret_header_rejected_without_linking() -> None:
    mock_config_repo = MagicMock()
    app = _build_app(config_repo=mock_config_repo)
    client = TestClient(app, raise_server_exceptions=False)

    response = client.post(
        "/notifications/telegram/webhook",
        json={"message": {"text": "/start abc", "chat": {"id": 1}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong-secret"},
    )

    assert response.status_code == 401
    mock_config_repo.save.assert_not_called()


def test_webhook_valid_start_message_stores_recipient_and_confirms() -> None:
    user_id = uuid4()
    token = generate_link_token(user_id)
    mock_config_repo = MagicMock()
    mock_channel = MagicMock()
    mock_preferences_repo = MagicMock()
    mock_preferences_repo.find_by_user_id.return_value = _make_preferences(user_id, preferred_notification_channel=None)
    app = _build_app(
        config_repo=mock_config_repo,
        notification_channels={"telegram": mock_channel},
        preferences_repo=mock_preferences_repo,
    )
    client = TestClient(app)

    response = client.post(
        "/notifications/telegram/webhook",
        json={"message": {"text": f"/start {token}", "chat": {"id": 42}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": _WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    mock_config_repo.save.assert_called_once()
    args, _kwargs = mock_config_repo.save.call_args
    assert args[0] == user_id
    assert args[1] == "telegram"
    assert args[2].data == {"chat_id": 42}
    mock_channel.send.assert_called_once()
    mock_preferences_repo.set_preferred_notification_channel.assert_called_once_with(user_id, "telegram")


def test_webhook_confirmation_localized_to_notification_language() -> None:
    user_id = uuid4()
    token = generate_link_token(user_id)
    mock_config_repo = MagicMock()
    mock_channel = MagicMock()
    mock_preferences_repo = MagicMock()
    mock_preferences_repo.find_by_user_id.return_value = _make_preferences(
        user_id, preferred_notification_channel="telegram", notification_language="es"
    )
    app = _build_app(
        config_repo=mock_config_repo,
        notification_channels={"telegram": mock_channel},
        preferences_repo=mock_preferences_repo,
    )
    client = TestClient(app)

    response = client.post(
        "/notifications/telegram/webhook",
        json={"message": {"text": f"/start {token}", "chat": {"id": 42}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": _WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    mock_channel.send.assert_called_once()
    args, _kwargs = mock_channel.send.call_args
    assert args[1].text == "✅ ¡Vinculado!"


def test_webhook_confirmation_falls_back_to_default_language_when_unset() -> None:
    user_id = uuid4()
    token = generate_link_token(user_id)
    mock_config_repo = MagicMock()
    mock_channel = MagicMock()
    mock_preferences_repo = MagicMock()
    mock_preferences_repo.find_by_user_id.return_value = _make_preferences(
        user_id, preferred_notification_channel=None, notification_language=None
    )
    app = _build_app(
        config_repo=mock_config_repo,
        notification_channels={"telegram": mock_channel},
        preferences_repo=mock_preferences_repo,
    )
    client = TestClient(app)

    response = client.post(
        "/notifications/telegram/webhook",
        json={"message": {"text": f"/start {token}", "chat": {"id": 42}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": _WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    mock_channel.send.assert_called_once()
    args, _kwargs = mock_channel.send.call_args
    assert args[1].text == "✅ Linked!"


def test_webhook_does_not_override_an_existing_preference() -> None:
    user_id = uuid4()
    token = generate_link_token(user_id)
    mock_config_repo = MagicMock()
    mock_channel = MagicMock()
    mock_preferences_repo = MagicMock()
    mock_preferences_repo.find_by_user_id.return_value = _make_preferences(
        user_id, preferred_notification_channel="other"
    )
    app = _build_app(
        config_repo=mock_config_repo,
        notification_channels={"telegram": mock_channel},
        preferences_repo=mock_preferences_repo,
    )
    client = TestClient(app)

    response = client.post(
        "/notifications/telegram/webhook",
        json={"message": {"text": f"/start {token}", "chat": {"id": 42}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": _WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    mock_preferences_repo.set_preferred_notification_channel.assert_not_called()


def test_webhook_expired_or_tampered_token_rejected_without_storing() -> None:
    mock_config_repo = MagicMock()
    mock_channel = MagicMock()
    app = _build_app(config_repo=mock_config_repo, notification_channels={"telegram": mock_channel})
    client = TestClient(app)

    response = client.post(
        "/notifications/telegram/webhook",
        json={"message": {"text": "/start not-a-valid-token", "chat": {"id": 42}}},
        headers={"X-Telegram-Bot-Api-Secret-Token": _WEBHOOK_SECRET},
    )

    assert response.status_code == 200
    mock_config_repo.save.assert_not_called()
    mock_channel.send.assert_not_called()


# ---------------------------------------------------------------------------
# GET /notifications/channels
# ---------------------------------------------------------------------------


def test_list_channels_unauthenticated_returns_401() -> None:
    mock_uc = MagicMock()
    mock_repo = MagicMock()
    mock_repo.find_by_id.return_value = None
    client = TestClient(_build_app(list_channels_uc=mock_uc, user_repo=mock_repo), raise_server_exceptions=False)

    response = client.get("/notifications/channels")

    assert response.status_code == 401
    mock_uc.execute.assert_not_called()


def test_list_channels_returns_configured_channels() -> None:
    mock_uc = MagicMock()
    mock_uc.execute.return_value = ["telegram"]
    app, cookie = _build_authed_app(list_channels_uc=mock_uc)
    client = TestClient(app)

    response = client.get("/notifications/channels", cookies={"session": cookie})

    assert response.status_code == 200
    assert response.json() == {"channels": ["telegram"]}
    mock_uc.execute.assert_called_once_with(_OWNER_ID)


def test_list_channels_returns_empty_list() -> None:
    mock_uc = MagicMock()
    mock_uc.execute.return_value = []
    app, cookie = _build_authed_app(list_channels_uc=mock_uc)
    client = TestClient(app)

    response = client.get("/notifications/channels", cookies={"session": cookie})

    assert response.status_code == 200
    assert response.json() == {"channels": []}


# ---------------------------------------------------------------------------
# DELETE /notifications/channels/{channel}
# ---------------------------------------------------------------------------


def test_delete_channel_unauthenticated_returns_401_without_contacting_use_case() -> None:
    mock_uc = MagicMock()
    mock_repo = MagicMock()
    mock_repo.find_by_id.return_value = None
    client = TestClient(_build_app(remove_channel_uc=mock_uc, user_repo=mock_repo), raise_server_exceptions=False)

    response = client.delete("/notifications/channels/telegram")

    assert response.status_code == 401
    mock_uc.execute.assert_not_called()


def test_delete_channel_returns_204() -> None:
    mock_uc = MagicMock()
    app, cookie = _build_authed_app(remove_channel_uc=mock_uc)
    client = TestClient(app)

    response = client.delete("/notifications/channels/telegram", cookies={"session": cookie})

    assert response.status_code == 204
    assert response.content == b""
    mock_uc.execute.assert_called_once_with(user_id=_OWNER_ID, channel="telegram")


# ---------------------------------------------------------------------------
# GET /notifications/available-channels
# ---------------------------------------------------------------------------


def test_available_channels_unauthenticated_returns_401() -> None:
    mock_repo = MagicMock()
    mock_repo.find_by_id.return_value = None
    client = TestClient(
        _build_app(user_repo=mock_repo, notification_channels={"telegram": MagicMock()}),
        raise_server_exceptions=False,
    )

    response = client.get("/notifications/available-channels")

    assert response.status_code == 401


def test_available_channels_returns_registered_channels() -> None:
    app, cookie = _build_authed_app(notification_channels={"telegram": MagicMock()})
    client = TestClient(app)

    response = client.get("/notifications/available-channels", cookies={"session": cookie})

    assert response.status_code == 200
    assert response.json() == {"channels": ["telegram"]}
