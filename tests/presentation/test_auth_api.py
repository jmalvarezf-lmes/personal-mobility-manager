"""
Integration tests for the auth API endpoints.

GET  /auth/me              (task 16.6)
POST /auth/logout          (task 16.7)
GET  /auth/google/callback (task 9.8 — rate limit only; full OAuth flow coverage is out of scope here)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from mobility_manager.domain.entities.user import User
from mobility_manager.presentation.api.csrf import generate_signed_state
from mobility_manager.presentation.api.limiter import limiter
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


def _build_app(
    user_repo: MagicMock | None = None,
    authenticate_uc: MagicMock | None = None,
    with_rate_limiting: bool = False,
) -> FastAPI:
    app = FastAPI()
    if with_rate_limiting:
        app.state.limiter = limiter
        app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
        app.add_middleware(SlowAPIMiddleware)
    app.include_router(router)
    if user_repo is not None:
        app.state.user_repo = user_repo
    if authenticate_uc is not None:
        app.state.authenticate_google_user = authenticate_uc
    return app


def _mock_google_httpx_client() -> MagicMock:
    """
    Mock the `httpx.AsyncClient` used by google_callback for both the token
    exchange (POST) and the userinfo lookup (GET), returning a successful
    exchange each time it's used as an async context manager.
    """
    token_response = MagicMock()
    token_response.raise_for_status = MagicMock()
    token_response.json.return_value = {"access_token": "mock-access-token"}

    userinfo_response = MagicMock()
    userinfo_response.raise_for_status = MagicMock()
    userinfo_response.json.return_value = {
        "sub": "google-sub-123",
        "email": "user@example.com",
        "name": "Test User",
    }

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=token_response)
    mock_client.get = AsyncMock(return_value=userinfo_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return mock_client


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


# ---------------------------------------------------------------------------
# GET /auth/google/callback — Task 9.8 (rate limit only)
# ---------------------------------------------------------------------------


class TestGoogleCallbackRateLimit:
    def test_rate_limit_returns_429_on_the_61st_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Task 9.8: 60/minute is enforced on GET /auth/google/callback (task 5.4)."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.com/auth/google/callback")
        limiter.reset()
        try:
            mock_authenticate_uc = MagicMock()
            mock_authenticate_uc.execute.return_value = _make_user()
            app = _build_app(authenticate_uc=mock_authenticate_uc, with_rate_limiting=True)
            client = TestClient(app, follow_redirects=False)

            state = generate_signed_state()
            mock_client = _mock_google_httpx_client()

            last_status = None
            with patch(
                "mobility_manager.presentation.api.routers.auth.httpx.AsyncClient",
                return_value=mock_client,
            ):
                for _ in range(61):
                    response = client.get(
                        "/auth/google/callback",
                        params={"code": "auth-code", "state": state},
                    )
                    last_status = response.status_code

            assert last_status == 429
        finally:
            limiter.reset()
