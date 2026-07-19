"""
Presentation tests for GET/POST/DELETE /vehicles/{id}/ser-parking-exemptions.

Covers every scenario in the vehicle-ser-parking-exemption spec's endpoint
requirements: auth, ownership, not-found, upsert-replaces, invalid zone,
idempotent delete.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.user import User
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_ser_parking_exemption import (
    VehicleSerParkingExemption,
)
from mobility_manager.domain.exceptions import InvalidSerParkingExemptionZoneError
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.presentation.api.routers.vehicles import router

_JWT_SECRET = "test-secret-for-ser-parking-exemptions"
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


def _make_vehicle(vehicle_id: UUID, user_id: UUID) -> Vehicle:
    return Vehicle(
        id=vehicle_id,
        brand=Brand.GENERIC,
        display_name="Test Vehicle",
        vin=None,
        license_plate="1234ABC",
        created_at=datetime.now(UTC),
        user_id=user_id,
    )


def _build_app(
    vehicle_repo=None,
    user_repo=None,
    get_uc=None,
    set_uc=None,
    clear_uc=None,
) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if vehicle_repo is not None:
        app.state.vehicle_repo = vehicle_repo
    if user_repo is not None:
        app.state.user_repo = user_repo
    if get_uc is not None:
        app.state.get_vehicle_ser_parking_exemption = get_uc
    if set_uc is not None:
        app.state.set_vehicle_ser_parking_exemption = set_uc
    if clear_uc is not None:
        app.state.clear_vehicle_ser_parking_exemption = clear_uc
    return app


def _build_authed_app(vehicle=None, **kwargs) -> tuple[FastAPI, str]:
    """Build app with a user_repo/vehicle_repo returning the test user/vehicle, and return (app, cookie)."""
    user = _make_test_user()
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_id.return_value = user
    kwargs.setdefault("user_repo", mock_user_repo)

    mock_vehicle_repo = MagicMock()
    mock_vehicle_repo.get_by_id.return_value = vehicle
    kwargs.setdefault("vehicle_repo", mock_vehicle_repo)

    app = _build_app(**kwargs)
    cookie = _make_session_cookie(user)
    return app, cookie


# ---------------------------------------------------------------------------
# GET /vehicles/{id}/ser-parking-exemptions
# ---------------------------------------------------------------------------


class TestGetSerParkingExemption:
    def test_unauthenticated_returns_401(self) -> None:
        app = _build_app()
        client = TestClient(app)

        response = client.get(f"/vehicles/{uuid4()}/ser-parking-exemptions")

        assert response.status_code == 401

    def test_non_existent_vehicle_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app, cookie = _build_authed_app(vehicle=None)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.get(f"/vehicles/{uuid4()}/ser-parking-exemptions")

        assert response.status_code == 404

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        other_owner_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, other_owner_id)
        app, cookie = _build_authed_app(vehicle=vehicle)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.get(f"/vehicles/{vehicle_id}/ser-parking-exemptions")

        assert response.status_code == 403

    def test_owner_retrieves_existing_exemption(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        get_uc = MagicMock()
        get_uc.execute.return_value = VehicleSerParkingExemption(
            vehicle_id=vehicle_id,
            city_code="madrid",
            zone_number="163",
            updated_at=datetime.now(UTC),
        )
        app, cookie = _build_authed_app(vehicle=vehicle, get_uc=get_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.get(f"/vehicles/{vehicle_id}/ser-parking-exemptions")

        assert response.status_code == 200
        assert response.json() == {"city_code": "madrid", "zone_number": "163"}

    def test_owner_retrieves_when_no_exemption_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        get_uc = MagicMock()
        get_uc.execute.return_value = None
        app, cookie = _build_authed_app(vehicle=vehicle, get_uc=get_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.get(f"/vehicles/{vehicle_id}/ser-parking-exemptions")

        assert response.status_code == 200
        assert response.json() == {"city_code": None, "zone_number": None}


# ---------------------------------------------------------------------------
# POST /vehicles/{id}/ser-parking-exemptions
# ---------------------------------------------------------------------------


class TestSetSerParkingExemption:
    def test_unauthenticated_returns_401(self) -> None:
        app = _build_app()
        client = TestClient(app)

        response = client.post(
            f"/vehicles/{uuid4()}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "163"},
        )

        assert response.status_code == 401

    def test_non_existent_vehicle_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app, cookie = _build_authed_app(vehicle=None)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{uuid4()}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "163"},
        )

        assert response.status_code == 404

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        other_owner_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, other_owner_id)
        app, cookie = _build_authed_app(vehicle=vehicle)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{vehicle_id}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "163"},
        )

        assert response.status_code == 403

    def test_owner_sets_a_new_exemption(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        set_uc = MagicMock()
        set_uc.execute.return_value = VehicleSerParkingExemption(
            vehicle_id=vehicle_id,
            city_code="madrid",
            zone_number="163",
            updated_at=datetime.now(UTC),
        )
        app, cookie = _build_authed_app(vehicle=vehicle, set_uc=set_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{vehicle_id}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "163"},
        )

        assert response.status_code == 200
        assert response.json() == {"city_code": "madrid", "zone_number": "163"}
        set_uc.execute.assert_called_once_with(vehicle_id, "madrid", "163")

    def test_owner_replaces_existing_exemption(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        set_uc = MagicMock()
        set_uc.execute.return_value = VehicleSerParkingExemption(
            vehicle_id=vehicle_id,
            city_code="madrid",
            zone_number="200",
            updated_at=datetime.now(UTC),
        )
        app, cookie = _build_authed_app(vehicle=vehicle, set_uc=set_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{vehicle_id}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "200"},
        )

        assert response.status_code == 200
        assert response.json()["zone_number"] == "200"

    def test_unknown_zone_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        set_uc = MagicMock()
        set_uc.execute.side_effect = InvalidSerParkingExemptionZoneError("no such zone")
        app, cookie = _build_authed_app(vehicle=vehicle, set_uc=set_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{vehicle_id}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "999999"},
        )

        assert response.status_code == 422

    def test_zone_number_over_max_length_returns_422_without_reaching_use_case(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        set_uc = MagicMock()
        app, cookie = _build_authed_app(vehicle=vehicle, set_uc=set_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{vehicle_id}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "12345678901"},
        )

        assert response.status_code == 422
        set_uc.execute.assert_not_called()

    def test_city_code_over_max_length_returns_422_without_reaching_use_case(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        set_uc = MagicMock()
        app, cookie = _build_authed_app(vehicle=vehicle, set_uc=set_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{vehicle_id}/ser-parking-exemptions",
            json={"city_code": "m" * 51, "zone_number": "163"},
        )

        assert response.status_code == 422
        set_uc.execute.assert_not_called()

    def test_unrecognized_extra_field_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        set_uc = MagicMock()
        app, cookie = _build_authed_app(vehicle=vehicle, set_uc=set_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.post(
            f"/vehicles/{vehicle_id}/ser-parking-exemptions",
            json={"city_code": "madrid", "zone_number": "163", "extra_field": "nope"},
        )

        assert response.status_code == 422
        set_uc.execute.assert_not_called()


# ---------------------------------------------------------------------------
# DELETE /vehicles/{id}/ser-parking-exemptions
# ---------------------------------------------------------------------------


class TestClearSerParkingExemption:
    def test_unauthenticated_returns_401(self) -> None:
        app = _build_app()
        client = TestClient(app)

        response = client.delete(f"/vehicles/{uuid4()}/ser-parking-exemptions")

        assert response.status_code == 401

    def test_non_existent_vehicle_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        app, cookie = _build_authed_app(vehicle=None)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.delete(f"/vehicles/{uuid4()}/ser-parking-exemptions")

        assert response.status_code == 404

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        other_owner_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, other_owner_id)
        app, cookie = _build_authed_app(vehicle=vehicle)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.delete(f"/vehicles/{vehicle_id}/ser-parking-exemptions")

        assert response.status_code == 403

    def test_owner_clears_existing_exemption(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        clear_uc = MagicMock()
        app, cookie = _build_authed_app(vehicle=vehicle, clear_uc=clear_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.delete(f"/vehicles/{vehicle_id}/ser-parking-exemptions")

        assert response.status_code == 204
        clear_uc.execute.assert_called_once_with(vehicle_id)

    def test_clearing_when_none_set_is_a_no_op_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_vehicle(vehicle_id, _OWNER_ID)
        clear_uc = MagicMock()  # execute() is a no-op regardless of prior state
        app, cookie = _build_authed_app(vehicle=vehicle, clear_uc=clear_uc)
        client = TestClient(app)
        client.cookies.set("session", cookie)

        response = client.delete(f"/vehicles/{vehicle_id}/ser-parking-exemptions")

        assert response.status_code == 204
