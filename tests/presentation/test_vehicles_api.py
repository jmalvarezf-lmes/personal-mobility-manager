"""
Presentation tests for the vehicles API endpoints.

POST   /vehicles                       (task 16.9)
POST   /vehicles/{token}/location      (task 16.10)
GET    /vehicles/{vehicle_id}/location (task 16.11)
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from mobility_manager.application.use_cases.register_vehicle import (
    RegisterVehicleResult,
)
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.exceptions import (
    BrandNotEnabledError,
    VehicleLocationNotFoundError,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.routers.vehicles import router

_JWT_SECRET = "test-secret-for-vehicles"
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
    register_uc=None,
    record_uc=None,
    get_latest_uc=None,
    config_repo=None,
    user_repo=None,
    vehicle_repo=None,
) -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(router)
    if register_uc is not None:
        app.state.register_vehicle = register_uc
    if record_uc is not None:
        app.state.record_vehicle_location = record_uc
    if get_latest_uc is not None:
        app.state.get_latest_vehicle_location = get_latest_uc
    if config_repo is not None:
        app.state.vehicle_config_repo = config_repo
    if user_repo is not None:
        app.state.user_repo = user_repo
    if vehicle_repo is not None:
        app.state.vehicle_repo = vehicle_repo
    return app


def _build_authed_app(**kwargs) -> tuple[FastAPI, str]:
    """Build app with a user_repo that returns a test user and return (app, cookie)."""
    user = _make_test_user()
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_id.return_value = user
    kwargs.setdefault("user_repo", mock_user_repo)
    app = _build_app(**kwargs)
    cookie = _make_session_cookie(user)
    return app, cookie


def _make_vehicle_result(
    brand: Brand = Brand.GENERIC,
    token: str | None = None,
    vin: str | None = None,
) -> RegisterVehicleResult:
    return RegisterVehicleResult(
        vehicle_id=uuid4(),
        brand=brand,
        display_name="My Car",
        vin=vin,
        location_token=token or (str(uuid4()) if brand == Brand.GENERIC else None),
    )


def _make_location(vehicle_id: UUID | None = None, source: str = "pull") -> VehicleLocation:
    if vehicle_id is None:
        vehicle_id = uuid4()
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=40.4168,
        longitude=-3.7038,
        recorded_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source=source,  # type: ignore[arg-type]
    )


# ---------------------------------------------------------------------------
# POST /vehicles — Task 16.9 (now requires authentication)
# ---------------------------------------------------------------------------


class TestRegisterVehicle:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        client = TestClient(_build_app(register_uc=mock_uc, user_repo=mock_repo), raise_server_exceptions=False)

        response = client.post("/vehicles", json={"brand": "generic", "display_name": "My Car"})

        assert response.status_code == 401

    def test_register_generic_returns_201(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_vehicle_result(Brand.GENERIC)
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={"brand": "generic", "display_name": "My Car"},
            cookies={"session": cookie},
        )

        assert response.status_code == 201

    def test_register_generic_response_has_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        token = str(uuid4())
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_vehicle_result(Brand.GENERIC, token=token)
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={"brand": "generic", "display_name": "My Car"},
            cookies={"session": cookie},
        )

        assert response.json()["location_token"] == token

    def test_register_toyota_returns_201(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_vehicle_result(Brand.TOYOTA, vin="VIN001")
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "VIN001",
                "username": "u",
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 201

    def test_register_toyota_response_has_no_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_vehicle_result(Brand.TOYOTA, vin="VIN001")
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "VIN001",
                "username": "u",
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.json()["location_token"] is None

    def test_disabled_brand_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_uc.execute.side_effect = BrandNotEnabledError("Brand 'toyota' is not enabled")
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "VIN001",
                "username": "u",
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422

    def test_unknown_brand_string_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={"brand": "bmw", "display_name": "My BMW"},
            cookies={"session": cookie},
        )

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /vehicles/{token}/location — Task 16.10
# ---------------------------------------------------------------------------


class TestPushVehicleLocation:
    def _make_push_body(self, seconds_ago: float = 10) -> dict:
        recorded_at = datetime.now(UTC) - timedelta(seconds=seconds_ago)
        return {
            "lat": 40.4168,
            "lon": -3.7038,
            "recorded_at": recorded_at.isoformat(),
        }

    def test_valid_push_returns_204(self) -> None:
        token = str(uuid4())
        vehicle_id = uuid4()

        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = vehicle_id
        record_uc = MagicMock()

        client = TestClient(_build_app(record_uc=record_uc, config_repo=config_repo))
        response = client.post(f"/vehicles/{token}/location", json=self._make_push_body())

        assert response.status_code == 204

    def test_unknown_token_returns_404(self) -> None:
        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = None

        client = TestClient(_build_app(config_repo=config_repo))
        response = client.post("/vehicles/unknown-token/location", json=self._make_push_body())

        assert response.status_code == 404

    def test_lat_out_of_range_returns_422(self) -> None:
        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = uuid4()

        client = TestClient(_build_app(config_repo=config_repo))
        body = {"lat": 999.0, "lon": -3.7038, "recorded_at": datetime.now(UTC).isoformat()}
        response = client.post("/vehicles/some-token/location", json=body)

        assert response.status_code == 422

    def test_lon_out_of_range_returns_422(self) -> None:
        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = uuid4()

        client = TestClient(_build_app(config_repo=config_repo))
        body = {"lat": 40.4, "lon": 999.0, "recorded_at": datetime.now(UTC).isoformat()}
        response = client.post("/vehicles/some-token/location", json=body)

        assert response.status_code == 422

    def test_future_timestamp_returns_422(self) -> None:
        token = str(uuid4())
        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = uuid4()
        record_uc = MagicMock()
        record_uc.execute.side_effect = ValueError("recorded_at is more than 60s in the future")

        client = TestClient(_build_app(record_uc=record_uc, config_repo=config_repo))
        future = (datetime.now(UTC) + timedelta(seconds=120)).isoformat()
        body = {"lat": 40.4, "lon": -3.7, "recorded_at": future}
        response = client.post(f"/vehicles/{token}/location", json=body)

        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /vehicles/{vehicle_id}/location — Task 16.11 (now requires auth + ownership)
# ---------------------------------------------------------------------------


def _make_owned_vehicle(vehicle_id: UUID, owner_id: UUID) -> Vehicle:
    from datetime import UTC, datetime

    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="My Car",
        vin=None,
        created_at=datetime.now(UTC),
        user_id=owner_id,
    )


class TestGetLatestVehicleLocation:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        client = TestClient(
            _build_app(get_latest_uc=mock_uc, user_repo=mock_repo),
            raise_server_exceptions=False,
        )
        response = client.get(f"/vehicles/{uuid4()}/location")
        assert response.status_code == 401

    def test_found_returns_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        location = _make_location(vehicle_id=vehicle_id, source="pull")

        mock_uc = MagicMock()
        mock_uc.execute.return_value = location

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.find_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app)
        response = client.get(f"/vehicles/{vehicle_id}/location", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert data["latitude"] == pytest.approx(40.4168)
        assert data["source"] == "pull"

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        other_owner_id = uuid4()

        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.find_by_id.return_value = _make_owned_vehicle(vehicle_id, other_owner_id)

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f"/vehicles/{vehicle_id}/location", cookies={"session": cookie})

        assert response.status_code == 403

    def test_no_history_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()

        mock_uc = MagicMock()
        mock_uc.execute.side_effect = VehicleLocationNotFoundError("No history")

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.find_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f"/vehicles/{vehicle_id}/location", cookies={"session": cookie})

        assert response.status_code == 404

    def test_unknown_vehicle_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown vehicle (not in repo) should return 404."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)

        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.find_by_id.return_value = None

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f"/vehicles/{uuid4()}/location", cookies={"session": cookie})

        assert response.status_code == 404

    def test_response_includes_source_field(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        location = _make_location(vehicle_id=vehicle_id, source="push")

        mock_uc = MagicMock()
        mock_uc.execute.return_value = location

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.find_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app)
        response = client.get(f"/vehicles/{vehicle_id}/location", cookies={"session": cookie})

        assert response.json()["source"] == "push"

    def test_response_includes_vehicle_id(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        location = _make_location(vehicle_id=vehicle_id)

        mock_uc = MagicMock()
        mock_uc.execute.return_value = location

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.find_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app)
        response = client.get(f"/vehicles/{vehicle_id}/location", cookies={"session": cookie})

        assert UUID(response.json()["vehicle_id"]) == vehicle_id
