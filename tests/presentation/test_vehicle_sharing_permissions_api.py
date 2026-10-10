"""
Permission-matrix tests for vehicle-sharing endpoints.

For each affected endpoint we assert the status code for:
  - owner
  - sharee
  - non-accessor (authenticated user with no share)
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

from mobility_manager.application.use_cases.list_user_vehicles import (
    VehicleWithLocation,
)
from mobility_manager.domain.entities.city import City
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.entities.vehicle_share import VehicleShare
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.generic_config import GenericConfig
from mobility_manager.presentation.api.limiter import limiter
from mobility_manager.presentation.api.routers.vehicles import router

_JWT_SECRET = "test-secret-for-permissions"


@pytest.fixture()
def owner_id() -> UUID:
    return uuid4()


@pytest.fixture()
def sharee_id() -> UUID:
    return uuid4()


@pytest.fixture()
def other_user_id() -> UUID:
    return uuid4()


@pytest.fixture()
def vehicle_id() -> UUID:
    return uuid4()


@pytest.fixture()
def vehicle(owner_id: UUID, vehicle_id: UUID) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="Shared Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        owner_id=owner_id,
    )


@pytest.fixture()
def vehicle_location(vehicle_id: UUID) -> VehicleLocation:
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=40.4168,
        longitude=-3.7038,
        recorded_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source="push",  # type: ignore[arg-type]
    )


def _make_user(user_id: UUID, email: str) -> User:
    return User(
        id=user_id,
        google_sub=f"sub-{user_id}",
        email=email,
        display_name="Test User",
        created_at=datetime.now(UTC),
    )


def _make_cookie(user_id: UUID) -> str:
    payload = {
        "sub": str(user_id),
        "email": "user@example.com",
        "sid": str(uuid4()),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm="HS256")


def _make_vehicle_repo(vehicle: Vehicle) -> MagicMock:
    repo = MagicMock()
    repo.get_by_id.return_value = vehicle
    return repo


def _make_share_repo(sharee_id: UUID | None) -> MagicMock:
    repo = MagicMock()

    def find_by_vehicle_and_user(vehicle_id: UUID, user_id: UUID) -> VehicleShare | None:
        if sharee_id is not None and user_id == sharee_id:
            return VehicleShare(
                vehicle_id=vehicle_id,
                user_id=user_id,
                created_at=datetime.now(UTC),
            )
        return None

    repo.find_by_vehicle_and_user.side_effect = find_by_vehicle_and_user
    repo.list_sharees.return_value = []
    return repo


def _make_config_repo(vehicle_id: UUID) -> MagicMock:
    repo = MagicMock()
    repo.get_generic_config.return_value = GenericConfig(location_token=str(uuid4()))
    repo.get_toyota_config.return_value = MagicMock(username="u", locale="en")
    return repo


def _build_app(
    vehicle: Vehicle,
    sharee_id: UUID | None,
    list_uc: MagicMock | None = None,
) -> FastAPI:
    app = FastAPI()
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    app.include_router(router)

    app.state.vehicle_repo = _make_vehicle_repo(vehicle)
    app.state.vehicle_share_repo = _make_share_repo(sharee_id)
    app.state.vehicle_config_repo = _make_config_repo(vehicle.id)
    app.state.vehicle_ambient_label_repo = MagicMock()
    app.state.vehicle_ambient_label_repo.get_by_vehicle_id.return_value = None

    if list_uc is None:
        list_uc = MagicMock()
        list_uc.execute.return_value = []
    app.state.list_user_vehicles = list_uc

    app.state.get_latest_vehicle_location = MagicMock()
    app.state.get_latest_vehicle_location.execute.return_value = None

    app.state.list_vehicle_location_history = MagicMock()
    app.state.list_vehicle_location_history.execute.return_value = ([], False)

    app.state.list_ser_tickets = MagicMock()
    app.state.list_ser_tickets.execute.return_value = ([], False)

    city_repo = MagicMock()
    city_repo.list_all.return_value = [City(code="MAD", name="Madrid")]
    app.state.city_repo = city_repo

    app.state.get_vehicle_ser_parking_exemption = MagicMock()
    app.state.get_vehicle_ser_parking_exemption.execute.return_value = None

    app.state.delete_vehicle = MagicMock()
    app.state.update_vehicle = MagicMock()

    app.state.record_vehicle_location = MagicMock()

    app.state.set_vehicle_ser_parking_exemption = MagicMock()
    app.state.set_vehicle_ser_parking_exemption.execute.return_value = MagicMock(
        city_code="MAD", zone_number="1"
    )

    app.state.clear_vehicle_ser_parking_exemption = MagicMock()

    app.state.share_vehicle = MagicMock()
    app.state.share_vehicle.execute.return_value = MagicMock(
        user_id=uuid4(),
        display_name="Sharee",
        email="sharee@example.com",
        created_at=datetime.now(UTC),
    )

    app.state.list_vehicle_shares = MagicMock()
    app.state.list_vehicle_shares.execute.return_value = [
        MagicMock(
            user_id=uuid4(),
            display_name="Sharee",
            email="sharee@example.com",
            created_at=datetime.now(UTC),
        )
    ]

    app.state.revoke_vehicle_share = MagicMock()

    def _revoke_side_effect(vehicle_id: UUID, current_user_id: UUID, target_user_id: UUID) -> None:
        if current_user_id != vehicle.owner_id and current_user_id != target_user_id:
            raise PermissionError("Cannot revoke another user's share")

    app.state.revoke_vehicle_share.execute.side_effect = _revoke_side_effect

    mock_validate_session = MagicMock()
    mock_validate_session.execute.return_value = True
    app.state.validate_session = mock_validate_session

    return app


def _build_client(app: FastAPI, user_id: UUID) -> TestClient:
    user_repo = MagicMock()
    user_repo.find_by_id.return_value = _make_user(user_id, "user@example.com")
    app.state.user_repo = user_repo
    return TestClient(app, cookies={"session": _make_cookie(user_id)}, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# GET /vehicles
# ---------------------------------------------------------------------------


class TestListVehiclesPermissions:
    def test_owner_sees_owned_vehicle(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        list_uc = MagicMock()
        list_uc.execute.return_value = [
            VehicleWithLocation(vehicle=vehicle, location=None, has_ser_tickets=False, is_owner=True)
        ]
        app = _build_app(vehicle, sharee_id=None, list_uc=list_uc)
        client = _build_client(app, owner_id)

        response = client.get("/vehicles")

        assert response.status_code == 200
        assert response.json()[0]["is_owner"] is True

    def test_sharee_sees_shared_vehicle_not_owner(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        list_uc = MagicMock()
        list_uc.execute.return_value = [
            VehicleWithLocation(vehicle=vehicle, location=None, has_ser_tickets=False, is_owner=False)
        ]
        app = _build_app(vehicle, sharee_id=sharee_id, list_uc=list_uc)
        client = _build_client(app, sharee_id)

        response = client.get("/vehicles")

        assert response.status_code == 200
        assert response.json()[0]["is_owner"] is False


# ---------------------------------------------------------------------------
# GET /vehicles/{id}
# ---------------------------------------------------------------------------


class TestGetVehiclePermissions:
    def test_owner_sees_config(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.get(f"/vehicles/{vehicle.id}")

        assert response.status_code == 200
        assert response.json()["is_owner"] is True
        assert "location_token" in response.json()["config"]

    def test_sharee_sees_redacted_config(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.get(f"/vehicles/{vehicle.id}")

        assert response.status_code == 200
        assert response.json()["is_owner"] is False
        assert response.json()["config"] == {"redacted": True}

    def test_non_accessor_gets_404(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.get(f"/vehicles/{vehicle.id}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Read endpoints (location, history, ser-tickets, exemptions)
# ---------------------------------------------------------------------------


class TestReadEndpointPermissions:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "/location",
            "/locations",
            "/ser-tickets",
            "/ser-parking-exemptions",
        ],
    )
    def test_owner_gets_200(
        self,
        monkeypatch: pytest.MonkeyPatch,
        vehicle: Vehicle,
        owner_id: UUID,
        vehicle_location: VehicleLocation,
        endpoint: str,
    ) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        if endpoint == "/location":
            app.state.get_latest_vehicle_location.execute.return_value = vehicle_location  # type: ignore[attr-defined]
        client = _build_client(app, owner_id)

        response = client.get(f"/vehicles/{vehicle.id}{endpoint}")

        assert response.status_code == 200

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/location",
            "/locations",
            "/ser-tickets",
            "/ser-parking-exemptions",
        ],
    )
    def test_sharee_gets_200(
        self,
        monkeypatch: pytest.MonkeyPatch,
        vehicle: Vehicle,
        sharee_id: UUID,
        vehicle_location: VehicleLocation,
        endpoint: str,
    ) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        if endpoint == "/location":
            app.state.get_latest_vehicle_location.execute.return_value = vehicle_location  # type: ignore[attr-defined]
        client = _build_client(app, sharee_id)

        response = client.get(f"/vehicles/{vehicle.id}{endpoint}")

        assert response.status_code == 200

    @pytest.mark.parametrize(
        "endpoint",
        [
            "/location",
            "/locations",
            "/ser-tickets",
            "/ser-parking-exemptions",
        ],
    )
    def test_non_accessor_gets_404(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID, endpoint: str) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.get(f"/vehicles/{vehicle.id}{endpoint}")

        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Write endpoints (PUT, DELETE, locations, ser-parking-exemptions)
# ---------------------------------------------------------------------------


class TestWriteEndpointPermissions:
    def test_owner_update_gets_200(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        app.state.vehicle_repo.get_by_id.return_value = vehicle
        client = _build_client(app, owner_id)

        response = client.put(
            f"/vehicles/{vehicle.id}",
            json={"brand": "generic", "display_name": "Updated"},
        )

        assert response.status_code == 200

    def test_sharee_update_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.put(
            f"/vehicles/{vehicle.id}",
            json={"brand": "generic", "display_name": "Updated"},
        )

        assert response.status_code == 403

    def test_non_accessor_update_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.put(
            f"/vehicles/{vehicle.id}",
            json={"brand": "generic", "display_name": "Updated"},
        )

        assert response.status_code == 403

    def test_owner_delete_gets_204(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.delete(f"/vehicles/{vehicle.id}")

        assert response.status_code == 204

    def test_sharee_delete_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.delete(f"/vehicles/{vehicle.id}")

        assert response.status_code == 403

    def test_non_accessor_delete_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.delete(f"/vehicles/{vehicle.id}")

        assert response.status_code == 403

    def test_owner_submits_location_gets_204(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/locations",
            json={"lat": 40.4168, "lon": -3.7038, "recorded_at": datetime.now(UTC).isoformat()},
        )

        assert response.status_code == 204

    def test_sharee_submits_location_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/locations",
            json={"lat": 40.4168, "lon": -3.7038, "recorded_at": datetime.now(UTC).isoformat()},
        )

        assert response.status_code == 403

    def test_non_accessor_submits_location_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/locations",
            json={"lat": 40.4168, "lon": -3.7038, "recorded_at": datetime.now(UTC).isoformat()},
        )

        assert response.status_code == 403

    def test_owner_sets_exemption_gets_200(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/ser-parking-exemptions",
            json={"city_code": "MAD", "zone_number": "1"},
        )

        assert response.status_code == 200

    def test_sharee_sets_exemption_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/ser-parking-exemptions",
            json={"city_code": "MAD", "zone_number": "1"},
        )

        assert response.status_code == 403

    def test_non_accessor_sets_exemption_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/ser-parking-exemptions",
            json={"city_code": "MAD", "zone_number": "1"},
        )

        assert response.status_code == 403

    def test_owner_clears_exemption_gets_204(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.delete(f"/vehicles/{vehicle.id}/ser-parking-exemptions")

        assert response.status_code == 204

    def test_sharee_clears_exemption_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.delete(f"/vehicles/{vehicle.id}/ser-parking-exemptions")

        assert response.status_code == 403

    def test_non_accessor_clears_exemption_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.delete(f"/vehicles/{vehicle.id}/ser-parking-exemptions")

        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Share endpoints
# ---------------------------------------------------------------------------


class TestShareEndpointPermissions:
    def test_owner_lists_shares_gets_200(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.get(f"/vehicles/{vehicle.id}/shares")

        assert response.status_code == 200

    def test_sharee_lists_shares_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.get(f"/vehicles/{vehicle.id}/shares")

        assert response.status_code == 403

    def test_non_accessor_lists_shares_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.get(f"/vehicles/{vehicle.id}/shares")

        assert response.status_code == 403

    def test_owner_shares_vehicle_gets_201(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/shares",
            json={"email": "sharee@example.com"},
        )

        assert response.status_code == 201

    def test_sharee_shares_vehicle_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/shares",
            json={"email": "other@example.com"},
        )

        assert response.status_code == 403

    def test_non_accessor_shares_vehicle_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.post(
            f"/vehicles/{vehicle.id}/shares",
            json={"email": "other@example.com"},
        )

        assert response.status_code == 403

    def test_owner_revokes_share_gets_204(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, owner_id: UUID, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, owner_id)

        response = client.delete(f"/vehicles/{vehicle.id}/shares/{sharee_id}")

        assert response.status_code == 204

    def test_sharee_self_revokes_gets_204(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.delete(f"/vehicles/{vehicle.id}/shares/{sharee_id}")

        assert response.status_code == 204

    def test_sharee_revokes_other_gets_403(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, sharee_id: UUID, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=sharee_id)
        client = _build_client(app, sharee_id)

        response = client.delete(f"/vehicles/{vehicle.id}/shares/{other_user_id}")

        assert response.status_code == 403

    def test_non_accessor_revokes_gets_404(self, monkeypatch: pytest.MonkeyPatch, vehicle: Vehicle, other_user_id: UUID) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app = _build_app(vehicle, sharee_id=None)
        client = _build_client(app, other_user_id)

        response = client.delete(f"/vehicles/{vehicle.id}/shares/{other_user_id}")

        assert response.status_code == 404
