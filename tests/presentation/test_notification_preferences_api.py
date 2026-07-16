"""
Presentation tests for the notification type preferences API endpoints.

GET /notifications/types
GET /notifications/preferences
PUT /notifications/preferences/{type_key}
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.notification_type import NotificationType
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.user_notification_preference import (
    UserNotificationPreference,
)
from mobility_manager.presentation.api.routers.notification_preferences import router

_JWT_SECRET = "test-secret-for-notification-preferences"
_OWNER_ID = uuid4()

_THRESHOLD_SCHEMA = {"threshold_m": {"type": "integer", "min": 1}}


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


def _make_type(key: str, label: str) -> NotificationType:
    return NotificationType(key=key, label=label, config_schema=_THRESHOLD_SCHEMA)


def _make_preference(
    type_key: str,
    enabled: bool = False,
    config: dict | None = None,
    user_id: UUID | None = None,
) -> UserNotificationPreference:
    return UserNotificationPreference(
        user_id=user_id or _OWNER_ID,
        type_key=type_key,
        enabled=enabled,
        config=config or {},
        updated_at=datetime.now(UTC),
    )


def _build_app(user_repo=None, notification_preferences_repo=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if user_repo is not None:
        app.state.user_repo = user_repo
    if notification_preferences_repo is not None:
        app.state.notification_preferences_repo = notification_preferences_repo
    return app


def _build_authed_app(notification_preferences_repo=None) -> tuple[FastAPI, str]:
    user = _make_test_user()
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_id.return_value = user
    app = _build_app(user_repo=mock_user_repo, notification_preferences_repo=notification_preferences_repo)
    cookie = _make_session_cookie(user)
    return app, cookie


class TestListNotificationTypes:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = None
        client = TestClient(_build_app(user_repo=mock_user_repo), raise_server_exceptions=False)

        response = client.get("/notifications/types")

        assert response.status_code == 401

    def test_authenticated_returns_200_with_catalog(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        repo = MagicMock()
        repo.list_types.return_value = [
            _make_type("location_moved", "Vehicle moved"),
            _make_type("ser_zone_ticket_required", "SER ticket required"),
        ]
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app)

        response = client.get("/notifications/types", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        keys = {item["key"] for item in data}
        assert keys == {"location_moved", "ser_zone_ticket_required"}
        for item in data:
            assert item["config_schema"] == _THRESHOLD_SCHEMA


class TestGetNotificationPreferences:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = None
        client = TestClient(_build_app(user_repo=mock_user_repo), raise_server_exceptions=False)

        response = client.get("/notifications/preferences")

        assert response.status_code == 401

    def test_authenticated_returns_200_with_one_entry_per_type(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
        repo = MagicMock()
        repo.list_types.return_value = [
            _make_type("location_moved", "Vehicle moved"),
            _make_type("ser_zone_ticket_required", "SER ticket required"),
        ]
        repo.find_by_user_id.return_value = [
            _make_preference("location_moved", enabled=True, config={"threshold_m": 20}),
            _make_preference("ser_zone_ticket_required", enabled=False, config={}),
        ]
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app)

        response = client.get("/notifications/preferences", cookies={"session": cookie})

        assert response.status_code == 200
        data = {item["type_key"]: item for item in response.json()}
        assert data["location_moved"]["enabled"] is True
        assert data["location_moved"]["config"]["threshold_m"] == 20
        assert data["ser_zone_ticket_required"]["enabled"] is False
        # Missing threshold_m resolves via the env-var fallback.
        assert data["ser_zone_ticket_required"]["config"]["threshold_m"] == 50
        repo.find_by_user_id.assert_called_once_with(_OWNER_ID)

    def test_missing_row_for_a_catalog_type_still_returns_a_default_entry(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        monkeypatch.setenv("DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS", "50")
        repo = MagicMock()
        repo.list_types.return_value = [
            _make_type("location_moved", "Vehicle moved"),
            _make_type("ser_zone_ticket_required", "SER ticket required"),
        ]
        repo.find_by_user_id.return_value = []  # not provisioned yet
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app)

        response = client.get("/notifications/preferences", cookies={"session": cookie})

        assert response.status_code == 200
        data = {item["type_key"]: item for item in response.json()}
        assert data["location_moved"]["enabled"] is False
        assert data["location_moved"]["config"]["threshold_m"] == 50


class TestUpdateNotificationPreference:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = None
        client = TestClient(_build_app(user_repo=mock_user_repo), raise_server_exceptions=False)

        response = client.put(
            "/notifications/preferences/location_moved",
            json={"enabled": True, "config": {}},
        )

        assert response.status_code == 401

    def test_authenticated_disable_returns_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        repo = MagicMock()
        repo.list_types.return_value = [_make_type("ser_zone_ticket_required", "SER ticket required")]
        repo.update.return_value = _make_preference("ser_zone_ticket_required", enabled=False, config={})
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app)

        response = client.put(
            "/notifications/preferences/ser_zone_ticket_required",
            json={"enabled": False, "config": {}},
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["type_key"] == "ser_zone_ticket_required"
        assert data["enabled"] is False
        repo.update.assert_called_once_with(
            user_id=_OWNER_ID,
            type_key="ser_zone_ticket_required",
            enabled=False,
            config={},
        )

    def test_authenticated_customize_threshold_returns_200_with_new_value(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        repo = MagicMock()
        repo.list_types.return_value = [_make_type("location_moved", "Vehicle moved")]
        repo.update.return_value = _make_preference("location_moved", enabled=True, config={"threshold_m": 20})
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app)

        response = client.put(
            "/notifications/preferences/location_moved",
            json={"enabled": True, "config": {"threshold_m": 20}},
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        assert response.json()["config"]["threshold_m"] == 20

    def test_unknown_type_key_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        repo = MagicMock()
        repo.list_types.return_value = [_make_type("location_moved", "Vehicle moved")]
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            "/notifications/preferences/unknown_type",
            json={"enabled": True, "config": {}},
            cookies={"session": cookie},
        )

        assert response.status_code == 404
        repo.update.assert_not_called()

    def test_invalid_config_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        repo = MagicMock()
        repo.list_types.return_value = [_make_type("location_moved", "Vehicle moved")]
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            "/notifications/preferences/location_moved",
            json={"enabled": True, "config": {"threshold_m": -5}},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        repo.update.assert_not_called()

    def test_non_integer_config_value_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        repo = MagicMock()
        repo.list_types.return_value = [_make_type("location_moved", "Vehicle moved")]
        app, cookie = _build_authed_app(notification_preferences_repo=repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            "/notifications/preferences/location_moved",
            json={"enabled": True, "config": {"threshold_m": "not-a-number"}},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        repo.update.assert_not_called()
