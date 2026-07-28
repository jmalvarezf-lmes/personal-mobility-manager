"""
Presentation tests for the vehicles API endpoints.

POST   /vehicles                       (task 16.9)
POST   /vehicles/{token}/location      (task 16.10)
GET    /vehicles/{vehicle_id}/location (task 16.11)
GET    /vehicles                       (task 6.1)
GET    /vehicles/{id}                  (task 6.2)
DELETE /vehicles/{id}                  (task 6.3)
PUT    /vehicles/{id}                  (task 6.4)
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
from mobility_manager.domain.value_objects.generic_config import GenericConfig
from mobility_manager.domain.value_objects.toyota_config import ToyotaConfig
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
        "sid": str(uuid4()),
        "exp": datetime.now(UTC) + timedelta(hours=1),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _build_app(
    register_uc=None,
    record_uc=None,
    get_latest_uc=None,
    list_uc=None,
    delete_uc=None,
    update_uc=None,
    config_repo=None,
    user_repo=None,
    vehicle_repo=None,
    ambient_label_repo=None,
    list_history_uc=None,
    list_ser_tickets_uc=None,
    city_repo=None,
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
    if list_uc is not None:
        app.state.list_user_vehicles = list_uc
    if delete_uc is not None:
        app.state.delete_vehicle = delete_uc
    if update_uc is not None:
        app.state.update_vehicle = update_uc
    if config_repo is not None:
        app.state.vehicle_config_repo = config_repo
    if user_repo is not None:
        app.state.user_repo = user_repo
    if vehicle_repo is not None:
        app.state.vehicle_repo = vehicle_repo
    if ambient_label_repo is not None:
        app.state.vehicle_ambient_label_repo = ambient_label_repo
    if list_history_uc is not None:
        app.state.list_vehicle_location_history = list_history_uc
    if list_ser_tickets_uc is not None:
        app.state.list_ser_tickets = list_ser_tickets_uc
    if city_repo is not None:
        app.state.city_repo = city_repo
    mock_validate_session = MagicMock()
    mock_validate_session.execute.return_value = True
    app.state.validate_session = mock_validate_session
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
                "vin": "1HGCM82633A004352",
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
                "vin": "1HGCM82633A004352",
                "username": "u",
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.json()["location_token"] is None

    def test_register_response_includes_label_resolved_synchronously(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """
        RegisterVehicle's best-effort DGT lookup runs and persists synchronously
        before returning (design.md decision 4) — the registration response
        should reflect an already-resolved label immediately, not require a
        follow-up GET /vehicles to see it. Regression test for the bug where
        POST /vehicles never carried ambient_label at all, so a newly created
        vehicle showed no icon until the page was reloaded.
        """
        from mobility_manager.domain.entities.vehicle_ambient_label import (
            VehicleAmbientLabel,
        )
        from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
        from mobility_manager.domain.value_objects.ambient_label_status import (
            AmbientLabelStatus,
        )

        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_result = _make_vehicle_result(Brand.GENERIC)
        mock_uc = MagicMock()
        mock_uc.execute.return_value = vehicle_result
        mock_ambient_label_repo = MagicMock()
        mock_ambient_label_repo.get_by_vehicle_id.return_value = VehicleAmbientLabel(
            vehicle_id=vehicle_result.vehicle_id,
            label=AmbientLabel.ECO,
            status=AmbientLabelStatus.FOUND,
            last_checked_at=datetime.now(UTC),
        )
        app, cookie = _build_authed_app(register_uc=mock_uc, ambient_label_repo=mock_ambient_label_repo)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={"brand": "generic", "display_name": "My Car", "license_plate": "1234ABC"},
            cookies={"session": cookie},
        )

        assert response.json()["ambient_label"] == "ECO"

    def test_register_response_ambient_label_null_when_unresolved(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

        assert response.json()["ambient_label"] is None

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
                "vin": "1HGCM82633A004352",
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

    def test_unrecognized_extra_field_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """StrictRequestModel rejects unknown fields (task 1.4)."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={"brand": "generic", "display_name": "My Car", "is_admin": True},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_malformed_vin_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "TOO-SHORT",
                "username": "u",
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_well_formed_vin_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_vehicle_result(Brand.TOYOTA, vin="1HGCM82633A004352")
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "1HGCM82633A004352",
                "username": "u",
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 201

    def test_unrecognized_locale_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "1HGCM82633A004352",
                "username": "u",
                "password": "p",
                "locale": "xx-YY",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_recognized_locale_is_accepted(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_uc.execute.return_value = _make_vehicle_result(Brand.TOYOTA, vin="1HGCM82633A004352")
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "1HGCM82633A004352",
                "username": "u",
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 201

    def test_over_length_display_name_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={"brand": "generic", "display_name": "A" * 101},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_over_length_toyota_username_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "1HGCM82633A004352",
                "username": "u" * 101,
                "password": "p",
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_over_length_toyota_password_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        app, cookie = _build_authed_app(register_uc=mock_uc)
        client = TestClient(app)

        response = client.post(
            "/vehicles",
            json={
                "brand": "toyota",
                "display_name": "My Toyota",
                "vin": "1HGCM82633A004352",
                "username": "u",
                "password": "p" * 201,
                "locale": "en_GB",
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_rate_limit_returns_429_on_the_61st_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Task 5.5: 60/minute is enforced on POST /vehicles."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        limiter.reset()
        try:
            mock_uc = MagicMock()
            mock_uc.execute.return_value = _make_vehicle_result(Brand.GENERIC)
            app, cookie = _build_authed_app(register_uc=mock_uc)
            client = TestClient(app)

            last_status = None
            for _ in range(61):
                response = client.post(
                    "/vehicles",
                    json={"brand": "generic", "display_name": "My Car"},
                    cookies={"session": cookie},
                )
                last_status = response.status_code

            assert last_status == 429
        finally:
            limiter.reset()


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

    def test_unrecognized_extra_field_returns_422(self) -> None:
        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = uuid4()
        record_uc = MagicMock()

        client = TestClient(_build_app(record_uc=record_uc, config_repo=config_repo))
        body = {**self._make_push_body(), "is_admin": True}
        response = client.post("/vehicles/some-token/location", json=body)

        assert response.status_code == 422
        record_uc.execute.assert_not_called()

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

    def test_second_push_for_same_token_within_a_minute_returns_429(self) -> None:
        """
        Task 9.7 (4R review fix #2): the new per-vehicle-token 1/minute limit,
        stacked alongside the existing per-remote-address 60/minute limit.
        """
        token = str(uuid4())
        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = uuid4()
        record_uc = MagicMock()

        limiter.reset()
        try:
            client = TestClient(_build_app(record_uc=record_uc, config_repo=config_repo))

            first = client.post(f"/vehicles/{token}/location", json=self._make_push_body())
            second = client.post(f"/vehicles/{token}/location", json=self._make_push_body())

            assert first.status_code == 204
            assert second.status_code == 429
        finally:
            limiter.reset()

    def test_push_for_a_different_token_within_the_same_window_is_unaffected(self) -> None:
        """Task 9.7: the per-token limit tracks each token's own count separately."""
        token_a = str(uuid4())
        token_b = str(uuid4())
        config_repo = MagicMock()
        config_repo.find_vehicle_by_token.return_value = uuid4()
        record_uc = MagicMock()

        limiter.reset()
        try:
            client = TestClient(_build_app(record_uc=record_uc, config_repo=config_repo))

            response_a = client.post(f"/vehicles/{token_a}/location", json=self._make_push_body())
            response_b = client.post(f"/vehicles/{token_b}/location", json=self._make_push_body())

            assert response_a.status_code == 204
            assert response_b.status_code == 204
        finally:
            limiter.reset()


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
        license_plate=None,
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
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

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
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, other_owner_id)

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
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)
        response = client.get(f"/vehicles/{vehicle_id}/location", cookies={"session": cookie})

        assert response.status_code == 404

    def test_unknown_vehicle_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Unknown vehicle (not in repo) should return 404."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)

        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = None

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
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

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
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(get_latest_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app)
        response = client.get(f"/vehicles/{vehicle_id}/location", cookies={"session": cookie})

        assert UUID(response.json()["vehicle_id"]) == vehicle_id


# ---------------------------------------------------------------------------
# Helpers shared by new endpoint tests
# ---------------------------------------------------------------------------


def _make_full_vehicle(
    vehicle_id: UUID | None = None,
    owner_id: UUID | None = None,
    brand: Brand = Brand.GENERIC,
    license_plate: str | None = None,
) -> Vehicle:
    from datetime import UTC, datetime

    return Vehicle(
        id=vehicle_id or uuid4(),
        brand=brand,
        display_name="My Car",
        vin="VIN001" if brand == Brand.TOYOTA else None,
        license_plate=license_plate,
        created_at=datetime.now(UTC),
        user_id=owner_id or _OWNER_ID,
    )


# ---------------------------------------------------------------------------
# GET /vehicles — Task 7.5
# ---------------------------------------------------------------------------


class TestListVehicles:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        client = TestClient(
            _build_app(user_repo=mock_repo),
            raise_server_exceptions=False,
        )

        response = client.get("/vehicles")

        assert response.status_code == 401

    def test_empty_list_returns_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = []
        app, cookie = _build_authed_app(list_uc=mock_list_uc)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        assert response.status_code == 200
        assert response.json() == []

    def test_vehicles_returned_without_location(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = [VehicleWithLocation(vehicle=vehicle, location=None)]
        app, cookie = _build_authed_app(list_uc=mock_list_uc)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["location"] is None
        assert UUID(data[0]["vehicle_id"]) == vehicle_id

    def test_vehicles_returned_with_location(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        location = _make_location(vehicle_id=vehicle_id)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = [VehicleWithLocation(vehicle=vehicle, location=location)]
        app, cookie = _build_authed_app(list_uc=mock_list_uc)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        data = response.json()
        assert data[0]["location"]["latitude"] == pytest.approx(40.4168)

    def test_vehicle_with_resolved_label_includes_it(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mobility_manager.domain.entities.vehicle_ambient_label import (
            VehicleAmbientLabel,
        )
        from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
        from mobility_manager.domain.value_objects.ambient_label_status import (
            AmbientLabelStatus,
        )

        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = [VehicleWithLocation(vehicle=vehicle, location=None)]
        mock_ambient_label_repo = MagicMock()
        mock_ambient_label_repo.get_by_vehicle_id.return_value = VehicleAmbientLabel(
            vehicle_id=vehicle_id,
            label=AmbientLabel.B,
            status=AmbientLabelStatus.FOUND,
            last_checked_at=datetime.now(UTC),
        )
        app, cookie = _build_authed_app(list_uc=mock_list_uc, ambient_label_repo=mock_ambient_label_repo)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        assert response.json()[0]["ambient_label"] == "B"

    def test_vehicle_with_unresolved_label_reports_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mobility_manager.domain.entities.vehicle_ambient_label import (
            VehicleAmbientLabel,
        )
        from mobility_manager.domain.value_objects.ambient_label_status import (
            AmbientLabelStatus,
        )

        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = [VehicleWithLocation(vehicle=vehicle, location=None)]
        mock_ambient_label_repo = MagicMock()
        mock_ambient_label_repo.get_by_vehicle_id.return_value = VehicleAmbientLabel(
            vehicle_id=vehicle_id,
            label=None,
            status=AmbientLabelStatus.NOT_FOUND,
            last_checked_at=datetime.now(UTC),
        )
        app, cookie = _build_authed_app(list_uc=mock_list_uc, ambient_label_repo=mock_ambient_label_repo)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        assert response.json()[0]["ambient_label"] is None

    def test_vehicle_with_no_label_row_reports_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = [VehicleWithLocation(vehicle=vehicle, location=None)]
        mock_ambient_label_repo = MagicMock()
        mock_ambient_label_repo.get_by_vehicle_id.return_value = None
        app, cookie = _build_authed_app(list_uc=mock_list_uc, ambient_label_repo=mock_ambient_label_repo)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        assert response.json()[0]["ambient_label"] is None

    def test_vehicle_with_auto_created_ticket_reports_has_ser_tickets_true(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = [
            VehicleWithLocation(vehicle=vehicle, location=None, has_ser_tickets=True)
        ]
        app, cookie = _build_authed_app(list_uc=mock_list_uc)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        assert response.json()[0]["has_ser_tickets"] is True

    def test_vehicle_with_no_tickets_reports_has_ser_tickets_false(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        mock_list_uc = MagicMock()
        mock_list_uc.execute.return_value = [
            VehicleWithLocation(vehicle=vehicle, location=None, has_ser_tickets=False)
        ]
        app, cookie = _build_authed_app(list_uc=mock_list_uc)
        client = TestClient(app)

        response = client.get("/vehicles", cookies={"session": cookie})

        assert response.json()[0]["has_ser_tickets"] is False


# ---------------------------------------------------------------------------
# GET /vehicles/{vehicle_id} — Task 7.6
# ---------------------------------------------------------------------------


class TestGetVehicleDetail:
    def _make_config_repo(self, vehicle_id: UUID, brand: Brand) -> MagicMock:
        config_repo = MagicMock()
        if brand == Brand.TOYOTA:
            config_repo.get_toyota_config.return_value = ToyotaConfig(
                username="alice", password="s3cr3t", locale="en_GB", vin="VIN001"
            )
        else:
            config_repo.get_generic_config.return_value = GenericConfig(location_token="tok-123")
        return config_repo

    def test_owner_gets_200_generic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        config_repo = self._make_config_repo(vehicle_id, Brand.GENERIC)

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, config_repo=config_repo)
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert data["config"]["location_token"] == "tok-123"

    def test_owner_gets_200_toyota_with_masked_password(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.TOYOTA)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        config_repo = self._make_config_repo(vehicle_id, Brand.TOYOTA)

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, config_repo=config_repo)
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}", cookies={"session": cookie})

        assert response.status_code == 200
        assert response.json()["config"]["password"] == "●●●●●●●●"

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=uuid4())
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{vehicle_id}", cookies={"session": cookie})

        assert response.status_code == 403

    def test_not_found_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = None

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{uuid4()}", cookies={"session": cookie})

        assert response.status_code == 404

    def test_owner_gets_resolved_ambient_label(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from mobility_manager.domain.entities.vehicle_ambient_label import (
            VehicleAmbientLabel,
        )
        from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
        from mobility_manager.domain.value_objects.ambient_label_status import (
            AmbientLabelStatus,
        )

        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        config_repo = self._make_config_repo(vehicle_id, Brand.GENERIC)
        mock_ambient_label_repo = MagicMock()
        mock_ambient_label_repo.get_by_vehicle_id.return_value = VehicleAmbientLabel(
            vehicle_id=vehicle_id,
            label=AmbientLabel.ECO,
            status=AmbientLabelStatus.FOUND,
            last_checked_at=datetime.now(UTC),
        )

        app, cookie = _build_authed_app(
            vehicle_repo=mock_vehicle_repo, config_repo=config_repo, ambient_label_repo=mock_ambient_label_repo
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}", cookies={"session": cookie})

        assert response.json()["ambient_label"] == "ECO"

    def test_owner_gets_null_ambient_label_when_no_repo_wired(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        config_repo = self._make_config_repo(vehicle_id, Brand.GENERIC)

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, config_repo=config_repo)
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}", cookies={"session": cookie})

        assert response.json()["ambient_label"] is None


# ---------------------------------------------------------------------------
# DELETE /vehicles/{vehicle_id} — Task 7.7
# ---------------------------------------------------------------------------


class TestDeleteVehicle:
    def test_owner_deletes_returns_204(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        mock_delete_uc = MagicMock()

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, delete_uc=mock_delete_uc)
        client = TestClient(app)

        response = client.delete(f"/vehicles/{vehicle_id}", cookies={"session": cookie})

        assert response.status_code == 204
        mock_delete_uc.execute.assert_called_once_with(vehicle_id)

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=uuid4())
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.delete(f"/vehicles/{vehicle_id}", cookies={"session": cookie})

        assert response.status_code == 403

    def test_not_found_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = None

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.delete(f"/vehicles/{uuid4()}", cookies={"session": cookie})

        assert response.status_code == 404

    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        client = TestClient(
            _build_app(user_repo=mock_repo),
            raise_server_exceptions=False,
        )

        response = client.delete(f"/vehicles/{uuid4()}")

        assert response.status_code == 401


# ---------------------------------------------------------------------------
# PUT /vehicles/{vehicle_id} — Task 7.8
# ---------------------------------------------------------------------------


class TestUpdateVehicle:
    def _make_config_repo(self, vehicle_id: UUID, brand: Brand) -> MagicMock:
        config_repo = MagicMock()
        if brand == Brand.TOYOTA:
            config_repo.get_toyota_config.return_value = ToyotaConfig(
                username="alice", password="s3cr3t", locale="en_GB", vin="VIN001"
            )
        else:
            config_repo.get_generic_config.return_value = GenericConfig(location_token="tok-123")
        return config_repo

    def test_toyota_display_name_update_returns_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.TOYOTA)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        config_repo = self._make_config_repo(vehicle_id, Brand.TOYOTA)
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(
            vehicle_repo=mock_vehicle_repo,
            config_repo=config_repo,
            update_uc=mock_update_uc,
        )
        client = TestClient(app)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "toyota", "display_name": "Updated", "username": "alice", "locale": "en_GB"},
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        mock_update_uc.execute.assert_called_once()

    def test_generic_display_name_update_returns_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        config_repo = self._make_config_repo(vehicle_id, Brand.GENERIC)
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(
            vehicle_repo=mock_vehicle_repo,
            config_repo=config_repo,
            update_uc=mock_update_uc,
        )
        client = TestClient(app)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "Updated Generic"},
            cookies={"session": cookie},
        )

        assert response.status_code == 200

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=uuid4())
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "Hacked"},
            cookies={"session": cookie},
        )

        assert response.status_code == 403

    def test_not_found_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = None

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{uuid4()}",
            json={"brand": "generic", "display_name": "New"},
            cookies={"session": cookie},
        )

        assert response.status_code == 404

    def test_unrecognized_locale_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.TOYOTA)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, update_uc=mock_update_uc)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "toyota", "display_name": "Updated", "username": "alice", "locale": "xx-YY"},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_update_uc.execute.assert_not_called()

    def test_unrecognized_extra_field_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, update_uc=mock_update_uc)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "My Car", "is_admin": True},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_update_uc.execute.assert_not_called()

    def test_over_length_display_name_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, update_uc=mock_update_uc)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "A" * 101},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_update_uc.execute.assert_not_called()

    def test_over_length_toyota_password_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.TOYOTA)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo, update_uc=mock_update_uc)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={
                "brand": "toyota",
                "display_name": "Updated",
                "username": "alice",
                "locale": "en_GB",
                "password": "p" * 201,
            },
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_update_uc.execute.assert_not_called()

    def test_set_license_plate_returns_200_with_plate(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        updated_vehicle = _make_full_vehicle(
            vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC, license_plate="1234ABC"
        )
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.side_effect = [vehicle, updated_vehicle]
        config_repo = self._make_config_repo(vehicle_id, Brand.GENERIC)
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(
            vehicle_repo=mock_vehicle_repo,
            config_repo=config_repo,
            update_uc=mock_update_uc,
        )
        client = TestClient(app)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "My Car", "license_plate": "1234ABC"},
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        assert response.json()["license_plate"] == "1234ABC"

    def test_license_plate_too_long_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        # get_owned_vehicle_or_raise is called manually inside the handler,
        # after `body` has already resolved — so an invalid body 422s via
        # normal FastAPI/Pydantic parameter binding before ownership is ever
        # checked, regardless of what vehicle_repo would return.
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "My Car", "license_plate": "A" * 21},
            cookies={"session": cookie},
        )

        assert response.status_code == 422

    def test_non_owner_with_invalid_body_returns_422_not_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """
        Task 9.3 (post-4R-review fix): body validation must still run before
        the ownership check for body-bearing routes. A non-owner sending a
        body that also fails Pydantic validation must get 422, not 403 —
        proving the fix in deps.py/routers/vehicles.py (calling
        get_owned_vehicle_or_raise manually, after `body` resolves) restores
        the original body-then-ownership ordering. See design.md decision 5
        amendment.
        """
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=uuid4(), brand=Brand.GENERIC)
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = vehicle
        app, cookie = _build_authed_app(vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "My Car", "license_plate": "A" * 21},
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_vehicle_repo.get_by_id.assert_not_called()

    def test_rate_limit_returns_429_on_the_61st_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Task 9.8: 60/minute is enforced on PUT /vehicles/{id} (task 5.2)."""
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        limiter.reset()
        try:
            vehicle_id = uuid4()
            vehicle = _make_full_vehicle(vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC)
            mock_vehicle_repo = MagicMock()
            mock_vehicle_repo.get_by_id.return_value = vehicle
            config_repo = self._make_config_repo(vehicle_id, Brand.GENERIC)
            mock_update_uc = MagicMock()

            app, cookie = _build_authed_app(
                vehicle_repo=mock_vehicle_repo,
                config_repo=config_repo,
                update_uc=mock_update_uc,
            )
            client = TestClient(app)

            last_status = None
            for _ in range(61):
                response = client.put(
                    f"/vehicles/{vehicle_id}",
                    json={"brand": "generic", "display_name": "My Car"},
                    cookies={"session": cookie},
                )
                last_status = response.status_code

            assert last_status == 429
        finally:
            limiter.reset()

    def test_clear_license_plate_returns_200_with_null(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        # Vehicle initially has a plate
        vehicle = _make_full_vehicle(
            vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC, license_plate="OLD"
        )
        # After update, plate is None
        updated_vehicle = _make_full_vehicle(
            vehicle_id=vehicle_id, owner_id=_OWNER_ID, brand=Brand.GENERIC, license_plate=None
        )
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.side_effect = [vehicle, updated_vehicle]
        config_repo = self._make_config_repo(vehicle_id, Brand.GENERIC)
        mock_update_uc = MagicMock()

        app, cookie = _build_authed_app(
            vehicle_repo=mock_vehicle_repo,
            config_repo=config_repo,
            update_uc=mock_update_uc,
        )
        client = TestClient(app)

        response = client.put(
            f"/vehicles/{vehicle_id}",
            json={"brand": "generic", "display_name": "My Car", "license_plate": None},
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        assert response.json()["license_plate"] is None


# ---------------------------------------------------------------------------
# GET /vehicles/{vehicle_id}/locations — paginated location history
# ---------------------------------------------------------------------------


class TestListLocationHistory:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        client = TestClient(
            _build_app(user_repo=mock_repo),
            raise_server_exceptions=False,
        )

        response = client.get(f"/vehicles/{uuid4()}/locations")

        assert response.status_code == 401

    def test_default_pagination_returns_5_items_and_has_more(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        locations = [_make_location(vehicle_id=vehicle_id) for _ in range(5)]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (locations, True)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/locations", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["has_more"] is True
        mock_uc.execute.assert_called_once_with(vehicle_id, limit=5, offset=0)

    def test_second_page_via_offset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        locations = [_make_location(vehicle_id=vehicle_id) for _ in range(3)]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (locations, False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app)

        response = client.get(
            f"/vehicles/{vehicle_id}/locations?limit=5&offset=5",
            cookies={"session": cookie},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["has_more"] is False
        mock_uc.execute.assert_called_once_with(vehicle_id, limit=5, offset=5)

    def test_limit_above_max_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(
            f"/vehicles/{vehicle_id}/locations?limit=51",
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_limit_zero_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(
            f"/vehicles/{vehicle_id}/locations?limit=0",
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_negative_offset_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(
            f"/vehicles/{vehicle_id}/locations?offset=-1",
            cookies={"session": cookie},
        )

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        other_owner_id = uuid4()

        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, other_owner_id)

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{vehicle_id}/locations", cookies={"session": cookie})

        assert response.status_code == 403
        mock_uc.execute.assert_not_called()

    def test_unknown_vehicle_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = None

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{uuid4()}/locations", cookies={"session": cookie})

        assert response.status_code == 404
        mock_uc.execute.assert_not_called()

    def test_zero_locations_returns_200_with_empty_items(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()

        mock_uc = MagicMock()
        mock_uc.execute.return_value = ([], False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_history_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/locations", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["has_more"] is False


# ---------------------------------------------------------------------------
# GET /vehicles/{vehicle_id}/ser-tickets — paginated SER ticket history
# ---------------------------------------------------------------------------


def _make_ser_ticket(
    vehicle_id: UUID | None = None,
    auto_created: bool | None = True,
    city_code: str | None = "madrid",
    latitude: float | None = 40.4168,
    longitude: float | None = -3.7038,
    start_date: datetime | None = None,
):
    from mobility_manager.domain.entities.parking_ticket import ParkingTicket

    created_at = datetime.now(UTC)
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id or uuid4(),
        user_id=_OWNER_ID,
        provider="elparking",
        duration_minutes=60,
        provider_reference="REF-001",
        cost=1.2,
        end_date=created_at + timedelta(hours=1),
        created_at=created_at,
        city_code=city_code,
        zone_number="163",
        latitude=latitude,
        longitude=longitude,
        auto_created=auto_created,
        # Every ticket ElParkingSerTicketProvider creates always has a real
        # start_date — default here to a distinct value (not created_at) so
        # tests can tell the two apart if they ever compare them.
        start_date=start_date or (created_at - timedelta(hours=1)),
    )


def _make_city_repo(cities: dict[str, str] | None = None) -> MagicMock:
    from mobility_manager.domain.entities.city import City

    repo = MagicMock()
    repo.list_all.return_value = [City(code=code, name=name) for code, name in (cities or {"madrid": "Madrid"}).items()]
    return repo


class TestListSerTickets:
    def test_unauthenticated_returns_401(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None
        client = TestClient(
            _build_app(user_repo=mock_repo),
            raise_server_exceptions=False,
        )

        response = client.get(f"/vehicles/{uuid4()}/ser-tickets")

        assert response.status_code == 401

    def test_owner_gets_200_with_items_and_has_more(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        tickets = [_make_ser_ticket(vehicle_id=vehicle_id) for _ in range(5)]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (tickets, True)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(
            list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo, city_repo=_make_city_repo()
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets?limit=5&offset=0", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 5
        assert data["has_more"] is True
        mock_uc.execute.assert_called_once_with(vehicle_id, limit=5, offset=0)

    def test_start_date_uses_ticket_start_date_not_created_at(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        real_start = datetime(2026, 7, 20, 9, 30, tzinfo=UTC)
        tickets = [_make_ser_ticket(vehicle_id=vehicle_id, start_date=real_start)]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (tickets, False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(
            list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo, city_repo=_make_city_repo()
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets", cookies={"session": cookie})

        assert datetime.fromisoformat(response.json()["items"][0]["start_date"]) == real_start
        assert datetime.fromisoformat(response.json()["items"][0]["start_date"]) != tickets[0].created_at

    def test_mixed_auto_created_and_manual_tickets_both_returned(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        tickets = [
            _make_ser_ticket(vehicle_id=vehicle_id, auto_created=True),
            _make_ser_ticket(vehicle_id=vehicle_id, auto_created=False),
        ]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (tickets, False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(
            list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo, city_repo=_make_city_repo()
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets", cookies={"session": cookie})

        data = response.json()
        assert {item["auto_created"] for item in data["items"]} == {True, False}

    def test_non_owner_returns_403(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        other_owner_id = uuid4()

        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, other_owner_id)

        app, cookie = _build_authed_app(list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets", cookies={"session": cookie})

        assert response.status_code == 403
        mock_uc.execute.assert_not_called()

    def test_unknown_vehicle_returns_404(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = None

        app, cookie = _build_authed_app(list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{uuid4()}/ser-tickets", cookies={"session": cookie})

        assert response.status_code == 404
        mock_uc.execute.assert_not_called()

    def test_zero_tickets_returns_200_with_empty_items(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()

        mock_uc = MagicMock()
        mock_uc.execute.return_value = ([], False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(
            list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo, city_repo=_make_city_repo()
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets", cookies={"session": cookie})

        assert response.status_code == 200
        data = response.json()
        assert data["items"] == []
        assert data["has_more"] is False

    def test_limit_above_max_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets?limit=51", cookies={"session": cookie})

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_negative_offset_returns_422(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        mock_uc = MagicMock()
        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo)
        client = TestClient(app, raise_server_exceptions=False)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets?offset=-1", cookies={"session": cookie})

        assert response.status_code == 422
        mock_uc.execute.assert_not_called()

    def test_known_city_code_resolves_city_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        tickets = [_make_ser_ticket(vehicle_id=vehicle_id, city_code="madrid")]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (tickets, False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(
            list_ser_tickets_uc=mock_uc,
            vehicle_repo=mock_vehicle_repo,
            city_repo=_make_city_repo({"madrid": "Madrid"}),
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets", cookies={"session": cookie})

        assert response.json()["items"][0]["city_name"] == "Madrid"

    def test_null_city_code_has_null_city_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        tickets = [_make_ser_ticket(vehicle_id=vehicle_id, city_code=None)]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (tickets, False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(
            list_ser_tickets_uc=mock_uc, vehicle_repo=mock_vehicle_repo, city_repo=_make_city_repo()
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets", cookies={"session": cookie})

        assert response.json()["items"][0]["city_code"] is None
        assert response.json()["items"][0]["city_name"] is None

    def test_unmatched_city_code_has_null_city_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)
        vehicle_id = uuid4()
        tickets = [_make_ser_ticket(vehicle_id=vehicle_id, city_code="unknown-city")]

        mock_uc = MagicMock()
        mock_uc.execute.return_value = (tickets, False)

        mock_vehicle_repo = MagicMock()
        mock_vehicle_repo.get_by_id.return_value = _make_owned_vehicle(vehicle_id, _OWNER_ID)

        app, cookie = _build_authed_app(
            list_ser_tickets_uc=mock_uc,
            vehicle_repo=mock_vehicle_repo,
            city_repo=_make_city_repo({"madrid": "Madrid"}),
        )
        client = TestClient(app)

        response = client.get(f"/vehicles/{vehicle_id}/ser-tickets", cookies={"session": cookie})

        assert response.json()["items"][0]["city_code"] == "unknown-city"
        assert response.json()["items"][0]["city_name"] is None
