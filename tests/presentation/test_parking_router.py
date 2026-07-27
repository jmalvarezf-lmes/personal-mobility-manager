"""
Presentation tests for the Parking API router.

GET /parking/ser-zone is pre-existing and not re-tested here. This file
covers POST /parking/ser-tickets: happy path (with and without explicit
lat/lng), and 404/409/502/401 error mappings.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.user import User
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderSessionNotFoundError,
    SerProviderVehicleNotFoundError,
    SerTicketProviderNotFoundError,
    SerZoneNotFoundError,
    VehicleLocationNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.presentation.api.routers.parking import router

_JWT_SECRET = "test-secret-for-parking-router"
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
        "sid": str(uuid4()),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _make_ticket(vehicle_id: UUID, duration_minutes: int) -> ParkingTicket:
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=_OWNER_ID,
        provider="elparking",
        duration_minutes=duration_minutes,
        provider_reference="REF-123",
        cost=1.5,
        end_date=datetime.now(UTC),
        created_at=datetime.now(UTC),
        city_code="madrid",
        zone_number="163",
    )


def _build_app(create_ser_ticket_uc=None, user_repo=None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    if create_ser_ticket_uc is not None:
        app.state.create_ser_ticket = create_ser_ticket_uc
    if user_repo is not None:
        app.state.user_repo = user_repo
    mock_validate_session = MagicMock()
    mock_validate_session.execute.return_value = True
    app.state.validate_session = mock_validate_session
    return app


def _build_authed_app(**kwargs) -> tuple[FastAPI, str]:
    user = _make_test_user()
    mock_user_repo = MagicMock()
    mock_user_repo.find_by_id.return_value = user
    kwargs.setdefault("user_repo", mock_user_repo)
    app = _build_app(**kwargs)
    cookie = _make_session_cookie(user)
    return app, cookie


_VEHICLE_ID = uuid4()
_VALID_BODY = {"vehicle_id": str(_VEHICLE_ID), "provider": "elparking", "duration_minutes": 60}


def test_unauthenticated_request_returns_401_without_contacting_use_case(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_repo = MagicMock()
    mock_repo.find_by_id.return_value = None
    client = TestClient(_build_app(create_ser_ticket_uc=mock_uc, user_repo=mock_repo), raise_server_exceptions=False)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY)

    assert response.status_code == 401
    mock_uc.execute.assert_not_called()


def test_successful_creation_with_explicit_location_returns_201(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    ticket = _make_ticket(_VEHICLE_ID, 60)
    mock_uc = MagicMock()
    mock_uc.execute.return_value = ticket
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    body = {**_VALID_BODY, "latitude": 40.4, "longitude": -3.7}
    response = client.post("/parking/ser-tickets", json=body, cookies={"session": cookie})

    assert response.status_code == 201
    payload = response.json()
    assert payload["id"] == str(ticket.id)
    assert payload["cost"] == ticket.cost
    assert payload["provider_reference"] == ticket.provider_reference
    assert payload["duration_minutes"] == ticket.duration_minutes

    _, kwargs = mock_uc.execute.call_args
    assert kwargs["user_id"] == _OWNER_ID
    assert kwargs["vehicle_id"] == _VEHICLE_ID
    assert kwargs["provider"] == "elparking"
    assert kwargs["duration_minutes"] == 60
    assert kwargs["location"].lat == 40.4
    assert kwargs["location"].lng == -3.7


def test_successful_creation_without_explicit_location_returns_201(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    ticket = _make_ticket(_VEHICLE_ID, 60)
    mock_uc = MagicMock()
    mock_uc.execute.return_value = ticket
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 201
    _, kwargs = mock_uc.execute.call_args
    assert kwargs["location"] is None


def test_vehicle_not_found_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = VehicleNotFoundError("not found")
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 404


def test_session_not_found_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerProviderSessionNotFoundError("no session")
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 404


def test_vehicle_not_present_in_provider_returns_409(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerProviderVehicleNotFoundError("no match")
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 409


def test_ser_zone_not_found_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerZoneNotFoundError("no zone")
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 404


def test_vehicle_location_not_found_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = VehicleLocationNotFoundError("no location history")
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 404


def test_unknown_provider_returns_404(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerTicketProviderNotFoundError("unknown provider")
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 404


def test_provider_api_error_returns_502(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    mock_uc.execute.side_effect = SerProviderApiError("upstream failure")
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post("/parking/ser-tickets", json=_VALID_BODY, cookies={"session": cookie})

    assert response.status_code == 502


def test_unrecognized_extra_field_returns_422(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
    mock_uc = MagicMock()
    app, cookie = _build_authed_app(create_ser_ticket_uc=mock_uc)
    client = TestClient(app)

    response = client.post(
        "/parking/ser-tickets", json={**_VALID_BODY, "is_admin": True}, cookies={"session": cookie}
    )

    assert response.status_code == 422
    mock_uc.execute.assert_not_called()
