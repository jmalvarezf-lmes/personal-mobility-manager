"""
Presentation tests for the preferences API endpoints.

GET /preferences
PUT /preferences
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
from mobility_manager.presentation.api.routers.preferences import router

_JWT_SECRET = "test-secret-for-preferences"
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
    user_id: UUID | None = None,
    default_ticket_duration_minutes: int = 60,
    auto_create_ticket: bool = False,
    preferred_notification_channel: str | None = None,
) -> UserPreferences:
    return UserPreferences(
        user_id=user_id or _OWNER_ID,
        default_ticket_duration_minutes=default_ticket_duration_minutes,
        auto_create_ticket=auto_create_ticket,
        preferred_notification_channel=preferred_notification_channel,
        updated_at=datetime.now(UTC),
    )


def _build_app(user_repo=None, preferences_repo=None, config_repo=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if user_repo is not None:
        app.state.user_repo = user_repo
    if preferences_repo is not None:
        app.state.user_preferences_repo = preferences_repo
    if config_repo is not None:
        app.state.user_notification_channel_config_repo = config_repo
    return app


def _build_authed_app(preferences_repo=None, config_repo=None) -> tuple[FastAPI, str]:
    user = _make_test_user()
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_id.return_value = user
    app = _build_app(user_repo=mock_user_repo, preferences_repo=preferences_repo, config_repo=config_repo)
    cookie = _make_session_cookie(user)
    return app, cookie


class TestGetPreferences:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = None
        client = TestClient(
            _build_app(user_repo=mock_user_repo),
            raise_server_exceptions=False,
        )

        response = client.get("/preferences")

        assert response.status_code == 401

    def test_authenticated_returns_200_with_preferences(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        preferences_repo = MagicMock()
        preferences_repo.find_by_user_id.return_value = _make_preferences(
            default_ticket_duration_minutes=60,
            auto_create_ticket=False,
            preferred_notification_channel="telegram",
        )
        app, cookie = _build_authed_app(preferences_repo=preferences_repo)
        client = TestClient(app)

        response = client.get("/preferences", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert data["default_ticket_duration_minutes"] == 60
        assert data["auto_create_ticket"] is False
        assert data["preferred_notification_channel"] == "telegram"
        preferences_repo.find_by_user_id.assert_called_once_with(_OWNER_ID)

    def test_missing_row_raises_assertion_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Login guarantees the row exists; a missing row is an unexpected failure, not 404."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        preferences_repo = MagicMock()
        preferences_repo.find_by_user_id.return_value = None
        app, cookie = _build_authed_app(preferences_repo=preferences_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get("/preferences", cookies={"session": cookie})

        assert response.status_code == 500


class TestUpdatePreferences:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = None
        client = TestClient(
            _build_app(user_repo=mock_user_repo),
            raise_server_exceptions=False,
        )

        response = client.put(
            "/preferences",
            json={
                "default_ticket_duration_minutes": 90,
                "auto_create_ticket": True,
                "preferred_notification_channel": None,
            },
        )

        assert response.status_code == 401

    def test_authenticated_update_returns_200_with_new_values(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        preferences_repo = MagicMock()
        preferences_repo.update.return_value = _make_preferences(
            default_ticket_duration_minutes=90,
            auto_create_ticket=True,
            preferred_notification_channel="telegram",
        )
        config_repo = MagicMock()
        config_repo.find.return_value = object()  # channel is connected
        app, cookie = _build_authed_app(preferences_repo=preferences_repo, config_repo=config_repo)
        client = TestClient(app)

        response = client.put(
            "/preferences",
            json={
                "default_ticket_duration_minutes": 90,
                "auto_create_ticket": True,
                "preferred_notification_channel": "telegram",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["default_ticket_duration_minutes"] == 90
        assert data["auto_create_ticket"] is True
        assert data["preferred_notification_channel"] == "telegram"
        config_repo.find.assert_called_once_with(_OWNER_ID, "telegram")
        preferences_repo.update.assert_called_once_with(
            user_id=_OWNER_ID,
            default_ticket_duration_minutes=90,
            auto_create_ticket=True,
            preferred_notification_channel="telegram",
        )

    def test_zero_duration_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        preferences_repo = MagicMock()
        app, cookie = _build_authed_app(preferences_repo=preferences_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            "/preferences",
            json={
                "default_ticket_duration_minutes": 0,
                "auto_create_ticket": False,
                "preferred_notification_channel": None,
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        preferences_repo.update.assert_not_called()

    def test_negative_duration_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        preferences_repo = MagicMock()
        app, cookie = _build_authed_app(preferences_repo=preferences_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            "/preferences",
            json={
                "default_ticket_duration_minutes": -10,
                "auto_create_ticket": False,
                "preferred_notification_channel": None,
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        preferences_repo.update.assert_not_called()

    def test_preferred_channel_not_configured_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        preferences_repo = MagicMock()
        config_repo = MagicMock()
        config_repo.find.return_value = None  # channel not connected
        app, cookie = _build_authed_app(preferences_repo=preferences_repo, config_repo=config_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            "/preferences",
            json={
                "default_ticket_duration_minutes": 90,
                "auto_create_ticket": True,
                "preferred_notification_channel": "telegram",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        config_repo.find.assert_called_once_with(_OWNER_ID, "telegram")
        preferences_repo.update.assert_not_called()

    def test_clearing_preferred_channel_with_null_is_allowed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        preferences_repo = MagicMock()
        preferences_repo.update.return_value = _make_preferences(
            default_ticket_duration_minutes=60,
            auto_create_ticket=False,
            preferred_notification_channel=None,
        )
        config_repo = MagicMock()
        app, cookie = _build_authed_app(preferences_repo=preferences_repo, config_repo=config_repo)
        client = TestClient(app)

        response = client.put(
            "/preferences",
            json={
                "default_ticket_duration_minutes": 60,
                "auto_create_ticket": False,
                "preferred_notification_channel": None,
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        assert response.json()["preferred_notification_channel"] is None
        config_repo.find.assert_not_called()
        preferences_repo.update.assert_called_once_with(
            user_id=_OWNER_ID,
            default_ticket_duration_minutes=60,
            auto_create_ticket=False,
            preferred_notification_channel=None,
        )
