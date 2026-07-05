"""
Presentation tests for the SER ticket providers API endpoints.

POST /ser-ticket-providers/connections
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderAuthenticationError,
    SerTicketProviderNotFoundError,
)
from mobility_manager.presentation.api.routers.ser_ticket_providers import router

_JWT_SECRET = "test-secret-for-ser-ticket-providers"
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


def _build_app(connect_uc=None, user_repo=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if connect_uc is not None:
        app.state.connect_ser_ticket_provider = connect_uc
    if user_repo is not None:
        app.state.user_repo = user_repo
    return app


def _build_authed_app(**kwargs) -> tuple[FastAPI, str]:
    user = _make_test_user()
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_id.return_value = user
    kwargs.setdefault("user_repo", mock_user_repo)
    app = _build_app(**kwargs)
    cookie = _make_session_cookie(user)
    return app, cookie


_VALID_BODY = {"provider": "elparking", "email": "alice@example.com", "password": "s3cr3t"}


def test_unauthenticated_request_returns_401_without_contacting_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_repo = MagicMock()
    mock_repo.find_by_id.return_value = None
    client = TestClient(_build_app(connect_uc=mock_uc, user_repo=mock_repo), raise_server_exceptions=False)

    response = client.post("/ser-ticket-providers/connections", json=_VALID_BODY)

    assert response.status_code == 401
    mock_uc.execute.assert_not_called()


def test_successful_connection_returns_204(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    app, cookie = _build_authed_app(connect_uc=mock_uc)
    client = TestClient(app)

    response = client.post(
        "/ser-ticket-providers/connections",
        json=_VALID_BODY,
        cookies={"session": cookie},
    )

    assert response.status_code == 204
    mock_uc.execute.assert_called_once()
    _, kwargs = mock_uc.execute.call_args
    assert kwargs["user_id"] == _OWNER_ID
    assert kwargs["provider"] == "elparking"
    assert kwargs["credentials"].data["email"] == "alice@example.com"
    assert kwargs["credentials"].data["uid"] == str(_OWNER_ID)
    assert kwargs["credentials"].data["model"] == "personal-mobility-manager-server"


def test_authentication_error_returns_401(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerProviderAuthenticationError("bad credentials")
    app, cookie = _build_authed_app(connect_uc=mock_uc)
    client = TestClient(app)

    response = client.post(
        "/ser-ticket-providers/connections",
        json=_VALID_BODY,
        cookies={"session": cookie},
    )

    assert response.status_code == 401


def test_api_error_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerProviderApiError("upstream failure")
    app, cookie = _build_authed_app(connect_uc=mock_uc)
    client = TestClient(app)

    response = client.post(
        "/ser-ticket-providers/connections",
        json=_VALID_BODY,
        cookies={"session": cookie},
    )

    assert response.status_code == 502


def test_unknown_provider_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerTicketProviderNotFoundError("unknown provider")
    app, cookie = _build_authed_app(connect_uc=mock_uc)
    client = TestClient(app)

    response = client.post(
        "/ser-ticket-providers/connections",
        json=_VALID_BODY,
        cookies={"session": cookie},
    )

    assert response.status_code == 404
