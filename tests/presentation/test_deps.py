"""
Unit tests for get_current_user FastAPI dependency.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.user import User
from mobility_manager.presentation.api.deps import get_current_user

_SECRET = "unit-test-secret"
_ALGORITHM = "HS256"


def _make_user(user_id=None) -> User:
    if user_id is None:
        user_id = uuid4()
    return User(
        id=user_id,
        google_sub="sub123",
        email="user@example.com",
        display_name="Test User",
        created_at=datetime.now(UTC),
    )


def _make_token(user: User, secret: str = _SECRET, exp_delta: int = 3600) -> str:
    payload = {
        "sub": str(user.id),
        "email": user.email,
        "exp": datetime.now(UTC) + timedelta(seconds=exp_delta),
    }
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)


class TestGetCurrentUser:
    """Test get_current_user directly via a minimal FastAPI route."""

    def _app_with_repo(self, user_repo: MagicMock) -> FastAPI:
        from fastapi import Depends

        app = FastAPI()
        app.state.user_repo = user_repo

        @app.get("/me")
        async def me(user: User = Depends(get_current_user)) -> dict:  # noqa: B008
            return {"id": str(user.id), "email": user.email}

        return app

    def test_valid_jwt_returns_user(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = user

        token = _make_token(user)
        client = TestClient(self._app_with_repo(mock_repo))
        response = client.get("/me", cookies={"session": token})

        assert response.status_code == 200
        assert response.json()["email"] == user.email

    def test_expired_jwt_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        user = _make_user()
        mock_repo = MagicMock()

        expired_token = _make_token(user, exp_delta=-10)
        client = TestClient(self._app_with_repo(mock_repo), raise_server_exceptions=False)
        response = client.get("/me", cookies={"session": expired_token})

        assert response.status_code == 401

    def test_missing_cookie_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        mock_repo = MagicMock()

        client = TestClient(self._app_with_repo(mock_repo), raise_server_exceptions=False)
        response = client.get("/me")

        assert response.status_code == 401

    def test_unknown_user_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        user = _make_user()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None  # user not found in DB

        token = _make_token(user)
        client = TestClient(self._app_with_repo(mock_repo), raise_server_exceptions=False)
        response = client.get("/me", cookies={"session": token})

        assert response.status_code == 401

    def test_tampered_token_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        user = _make_user()
        mock_repo = MagicMock()

        valid_token = _make_token(user)
        tampered = valid_token[:-4] + "XXXX"
        client = TestClient(self._app_with_repo(mock_repo), raise_server_exceptions=False)
        response = client.get("/me", cookies={"session": tampered})

        assert response.status_code == 401
