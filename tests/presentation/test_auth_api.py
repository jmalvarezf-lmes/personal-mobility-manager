"""
Integration tests for the auth API endpoints.

GET  /auth/me              (task 16.6)
POST /auth/logout          (task 16.7; extended in add-session-revocation
                             task 9.2/9.4 to cover server-side session revocation)
GET  /auth/google/callback (task 9.8 — rate limit only; full OAuth flow coverage is out of scope here;
                             extended in add-session-revocation task 9.1 to assert the sid claim)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from mobility_manager.application.use_cases.create_session import CreateSession
from mobility_manager.application.use_cases.revoke_session import RevokeSession
from mobility_manager.application.use_cases.validate_session import ValidateSession
from mobility_manager.domain.entities.session import Session
from mobility_manager.domain.entities.user import User
from mobility_manager.presentation.api.csrf import generate_signed_state
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.routers.auth import router

_JWT_SECRET = "test-auth-secret"
_ALGORITHM = "HS256"


class _FakeSessionRepository:
    """
    In-memory SessionRepository fake — lets CreateSession/RevokeSession/
    ValidateSession exercise real revocation semantics end-to-end within a
    single test, without a real database.
    """

    def __init__(self) -> None:
        self._sessions: dict[UUID, Session] = {}

    def create(self, user_id: UUID, expires_at: datetime) -> Session:
        session = Session(
            id=uuid4(),
            user_id=user_id,
            created_at=datetime.now(UTC),
            expires_at=expires_at,
            revoked_at=None,
        )
        self._sessions[session.id] = session
        return session

    def find_by_id(self, session_id: UUID) -> Session | None:
        return self._sessions.get(session_id)

    def revoke(self, session_id: UUID) -> None:
        session = self._sessions.get(session_id)
        if session is None:
            return
        self._sessions[session_id] = Session(
            id=session.id,
            user_id=session.user_id,
            created_at=session.created_at,
            expires_at=session.expires_at,
            revoked_at=datetime.now(UTC),
        )

    def delete_older_than(self, cutoff: datetime) -> int:
        raise NotImplementedError


def _make_user(user_id=None) -> User:
    return User(
        id=user_id or uuid4(),
        google_sub="sub123",
        email="test@example.com",
        display_name="Test User",
        created_at=datetime.now(UTC),
    )


def _make_token(user: User, sid: str | None = "sid-placeholder", secret: str = _JWT_SECRET, exp_delta: int = 3600) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.now(UTC) + timedelta(seconds=exp_delta),
    }
    if sid is not None:
        payload["sid"] = sid
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


def _build_app(
    user_repo: MagicMock | None = None,
    authenticate_uc: MagicMock | None = None,
    session_repo: _FakeSessionRepository | None = None,
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

    repo = session_repo if session_repo is not None else _FakeSessionRepository()
    app.state.create_session = CreateSession(session_repo=repo)
    app.state.revoke_session = RevokeSession(session_repo=repo)
    app.state.validate_session = ValidateSession(session_repo=repo)
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


def _make_valid_session_and_token(user: User, session_repo: _FakeSessionRepository) -> str:
    """Create a live session for `user` and return a JWT referencing it via `sid`."""
    session = session_repo.create(user_id=user.id, expires_at=datetime.now(UTC) + timedelta(hours=24))
    return _make_token(user, sid=str(session.id))


# ---------------------------------------------------------------------------
# GET /auth/me — Task 16.6
# ---------------------------------------------------------------------------


class TestGetMe:
    def test_valid_session_returns_200_with_user_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = user
        session_repo = _FakeSessionRepository()

        client = TestClient(_build_app(user_repo=mock_repo, session_repo=session_repo))
        token = _make_valid_session_and_token(user, session_repo)
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
        session_repo = _FakeSessionRepository()
        session = session_repo.create(user_id=user.id, expires_at=datetime.now(UTC) + timedelta(hours=24))
        expired_token = _make_token(user, sid=str(session.id), exp_delta=-10)

        client = TestClient(_build_app(user_repo=mock_repo, session_repo=session_repo), raise_server_exceptions=False)
        response = client.get("/auth/me", cookies={"session": expired_token})

        assert response.status_code == 401

    def test_tampered_token_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        session_repo = _FakeSessionRepository()
        valid_token = _make_valid_session_and_token(user, session_repo)
        tampered = valid_token[:-4] + "ZZZZ"

        client = TestClient(_build_app(user_repo=mock_repo, session_repo=session_repo), raise_server_exceptions=False)
        response = client.get("/auth/me", cookies={"session": tampered})

        assert response.status_code == 401

    def test_jwt_missing_sid_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A pre-change JWT (no sid claim) must be rejected — see spec scenario
        'JWT missing the sid claim is rejected'."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        token = _make_token(user, sid=None)

        client = TestClient(_build_app(user_repo=mock_repo), raise_server_exceptions=False)
        response = client.get("/auth/me", cookies={"session": token})

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# POST /auth/logout — Task 16.7
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logout_returns_204(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        session_repo = _FakeSessionRepository()
        token = _make_valid_session_and_token(user, session_repo)

        client = TestClient(_build_app(session_repo=session_repo))
        response = client.post("/auth/logout", cookies={"session": token})

        assert response.status_code == 204

    def test_logout_clears_session_cookie(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        session_repo = _FakeSessionRepository()
        token = _make_valid_session_and_token(user, session_repo)

        client = TestClient(_build_app(session_repo=session_repo))
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
        session_repo = _FakeSessionRepository()
        token = _make_valid_session_and_token(user, session_repo)

        client = TestClient(_build_app(user_repo=mock_repo, session_repo=session_repo), raise_server_exceptions=False)

        # Logout clears the cookie
        client.post("/auth/logout", cookies={"session": token})

        # Subsequent /me without session cookie returns 401
        response = client.get("/auth/me")
        assert response.status_code == 401

    def test_logout_revokes_the_session_so_replaying_the_cookie_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        Task 9.2: after POST /auth/logout, reusing the same (still
        non-expired) session cookie against a protected endpoint returns 401
        — the server-side session was revoked, not just the client cookie
        cleared.
        """
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = user
        session_repo = _FakeSessionRepository()
        token = _make_valid_session_and_token(user, session_repo)

        client = TestClient(_build_app(user_repo=mock_repo, session_repo=session_repo), raise_server_exceptions=False)

        logout_response = client.post("/auth/logout", cookies={"session": token})
        assert logout_response.status_code == 204

        # Replay the SAME still-cryptographically-valid, non-expired JWT.
        response = client.get("/auth/me", cookies={"session": token})
        assert response.status_code == 401

    def test_logout_with_malformed_cookie_still_returns_204(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Task 9.4 (decode-failure branch): a cookie that fails to decode must not error."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)

        client = TestClient(_build_app())
        response = client.post("/auth/logout", cookies={"session": "not-a-real-jwt"})

        assert response.status_code == 204

    def test_logout_still_returns_204_and_clears_cookie_when_revoke_raises(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        4R review fix 1: if revoke_session.execute() raises (e.g. a DB
        error), logout must still return 204 and clear the cookie instead
        of propagating a 500 — logout is best-effort.
        """
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        user = _make_user()
        session_repo = _FakeSessionRepository()
        token = _make_valid_session_and_token(user, session_repo)

        app = _build_app(session_repo=session_repo)
        app.state.revoke_session = MagicMock()
        app.state.revoke_session.execute.side_effect = RuntimeError("db is down")

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post("/auth/logout", cookies={"session": token})

        assert response.status_code == 204
        set_cookie = response.headers.get("set-cookie", "")
        assert "Max-Age=0" in set_cookie or "max-age=0" in set_cookie.lower()


# ---------------------------------------------------------------------------
# GET /auth/google/callback — Task 9.8 (rate limit) + add-session-revocation task 9.1
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


class TestGoogleCallbackCreatesSession:
    def test_callback_issues_jwt_with_sid_matching_a_new_session_row(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Task 9.1: google_callback's JWT payload includes a sid claim
        matching a newly created session row.
        """
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-client-id")
        monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "test-client-secret")
        monkeypatch.setenv("GOOGLE_REDIRECT_URI", "https://example.com/auth/google/callback")

        user = _make_user()
        mock_authenticate_uc = MagicMock()
        mock_authenticate_uc.execute.return_value = user
        session_repo = _FakeSessionRepository()

        app = _build_app(authenticate_uc=mock_authenticate_uc, session_repo=session_repo)
        client = TestClient(app, follow_redirects=False)

        state = generate_signed_state()
        mock_client = _mock_google_httpx_client()

        with patch(
            "mobility_manager.presentation.api.routers.auth.httpx.AsyncClient",
            return_value=mock_client,
        ):
            response = client.get(
                "/auth/google/callback",
                params={"code": "auth-code", "state": state},
            )

        assert response.status_code == 302
        cookie_value = response.cookies.get("session")
        assert cookie_value is not None

        payload = jwt.decode(cookie_value, _JWT_SECRET, algorithms=[_ALGORITHM])
        sid = payload.get("sid")
        assert sid is not None

        created_session = session_repo.find_by_id(UUID(sid))
        assert created_session is not None
        assert created_session.user_id == user.id
