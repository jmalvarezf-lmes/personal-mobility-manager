"""
Unit tests for get_current_user, require_owned_vehicle, and
get_owned_vehicle_or_raise FastAPI dependencies.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import jwt
import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.presentation.api.deps import (
    get_current_user,
    get_owned_vehicle_or_raise,
    require_owned_vehicle,
)

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


def _make_vehicle(vehicle_id, owner_id) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="My Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        user_id=owner_id,
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


# ---------------------------------------------------------------------------
# require_owned_vehicle (Depends target) and get_owned_vehicle_or_raise
# (plain function) — task 9.7.
#
# Both delegate to the same private _fetch_owned_vehicle helper, so the same
# three cases (not found / not owned / owned) apply to each entry point.
# Parametrized over which one is exercised rather than duplicating three
# near-identical test bodies per function.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("path", ["/owned-via-depends", "/owned-via-manual-call"])
class TestOwnershipDependencies:
    def _build_app(self, vehicle_repo: MagicMock, user_repo: MagicMock) -> FastAPI:
        from uuid import UUID

        from fastapi import Request

        app = FastAPI()
        app.state.vehicle_repo = vehicle_repo
        app.state.user_repo = user_repo

        @app.get("/owned-via-depends/{vehicle_id}")
        async def owned_via_depends(
            vehicle: Vehicle = Depends(require_owned_vehicle),  # noqa: B008
        ) -> dict:
            return {"id": str(vehicle.id)}

        @app.get("/owned-via-manual-call/{vehicle_id}")
        async def owned_via_manual_call(
            request: Request,
            vehicle_id: UUID,
            current_user: User = Depends(get_current_user),  # noqa: B008
        ) -> dict:
            vehicle = get_owned_vehicle_or_raise(request, vehicle_id, current_user)
            return {"id": str(vehicle.id)}

        return app

    def test_vehicle_not_found_returns_404(self, path: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        user = _make_user()
        vehicle_id = uuid4()

        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = user
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = None

        client = TestClient(
            self._build_app(mock_vehicle_repo, mock_user_repo), raise_server_exceptions=False
        )
        token = _make_token(user)
        response = client.get(f"{path}/{vehicle_id}", cookies={"session": token})

        assert response.status_code == 404

    def test_non_owner_returns_403(self, path: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        user = _make_user()
        vehicle_id = uuid4()
        other_owner_id = uuid4()

        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = user
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_vehicle(vehicle_id, other_owner_id)

        client = TestClient(
            self._build_app(mock_vehicle_repo, mock_user_repo), raise_server_exceptions=False
        )
        token = _make_token(user)
        response = client.get(f"{path}/{vehicle_id}", cookies={"session": token})

        assert response.status_code == 403

    def test_owner_returns_the_vehicle(self, path: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _SECRET)
        user = _make_user()
        vehicle_id = uuid4()

        mock_user_repo = MagicMock()
        mock_user_repo.find_by_id.return_value = user
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_vehicle(vehicle_id, user.id)

        client = TestClient(self._build_app(mock_vehicle_repo, mock_user_repo))
        token = _make_token(user)
        response = client.get(f"{path}/{vehicle_id}", cookies={"session": token})

        assert response.status_code == 200
        assert response.json()["id"] == str(vehicle_id)
