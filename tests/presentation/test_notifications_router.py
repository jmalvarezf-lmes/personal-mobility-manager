"""
Presentation tests for the notification channels API endpoints.

POST /notifications/telegram/link-code
POST /notifications/telegram/webhook
GET /notifications/channels
DELETE /notifications/channels/{channel}
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.user import User
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


def _build_app(
    generate_link_code_uc=None,
    list_channels_uc=None,
    remove_channel_uc=None,
    user_repo=None,
    config_repo=None,
    notification_channels=None,
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
    app = _build_app(config_repo=mock_config_repo, notification_channels={"telegram": mock_channel})
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
