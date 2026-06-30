"""
Integration tests for the auth API endpoints.

GET  /auth/me      (task 16.6)
POST /auth/logout  (task 16.7)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.user import User
from mobility_manager.presentation.api.routers.auth import router

_JWT_SECRET = "test-auth-secret"
_ALGORITHM = "HS256"


def _make_user(user_id=None) -> User:
    return User(
        id=user_id or uuid4(),
        google_sub="sub123",
        email="test@example.com",
        display_name="Test User",
        created_at=datetime.now(UTC),
    )


def _make_token(user: User, secret: str = _JWT_SECRET, exp_delta: int = 3600) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.now(UTC) + timedelta(seconds=exp_delta),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def _build_app(user_repo: MagicMock | None = None, authenticate_uc: MagicMock | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if user_repo is not None:
        app.state.user_repo = user_repo
    if authenticate_uc is not None:
        app.state.authenticate_google_user = authenticate_uc
    return app


# ---------------------------------------------------------------------------
# GET /auth/me — Task 16.6
# ---------------------------------------------------------------------------


class TestGetMe:
    def test_valid_session_returns_200_with_user_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = user

        client = TestClient(_build_app(user_repo=mock_repo))
        token = _make_token(user)
        response = client.get("/auth/me", cookies={"session": token})

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user.email
        assert data["display_name"] == user.display_name
        assert data["id"] == str(user.id)

    def test_no_cookie_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_repo = MagicMock()

        client = TestClient(_build_app(user_repo=mock_repo), raise_server_exceptions=False)
        response = client.get("/auth/me")

        assert response.status_code == 401

    def test_expired_token_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        expired_token = _make_token(user, exp_delta=-10)

        client = TestClient(_build_app(user_repo=mock_repo), raise_server_exceptions=False)
        response = client.get("/auth/me", cookies={"session": expired_token})

        assert response.status_code == 401

    def test_tampered_token_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        valid_token = _make_token(user)
        tampered = valid_token[:-4] + "ZZZZ"

        client = TestClient(_build_app(user_repo=mock_repo), raise_server_exceptions=False)
        response = client.get("/auth/me", cookies={"session": tampered})

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout — Task 16.7
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_returns_204(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        token = _make_token(user)

        client = TestClient(_build_app())
        response = client.post("/auth/logout", cookies={"session": token})

        assert response.status_code == 204

    def test_logout_clears_session_cookie(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        token = _make_token(user)

        client = TestClient(_build_app())
        response = client.post("/auth/logout", cookies={"session": token})

        # After logout the session cookie should have Max-Age=0 (cleared)
        set_cookie = response.headers.get("set-cookie", "")
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie.lower()

    def test_logout_without_cookie_returns_204(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)

        client = TestClient(_build_app())
        response = client.post("/auth/logout")

        assert response.status_code == 204

    def test_get_me_after_logout_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = user
        token = _make_token(user)

        client = TestClient(_build_app(user_repo=mock_repo), raise_server_exceptions=False)

        # Logout clears the cookie
        client.post("/auth/logout", cookies={"session": token})

        # Subsequent /me without session cookie returns 401
        response = client.get("/auth/me")
        assert response.status_code == 401
