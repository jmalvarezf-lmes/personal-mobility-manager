"""
Presentation tests for GET /parking/ser-zone endpoint.

Uses FastAPI TestClient with mocked use case via app.state.
"""
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.exceptions import SerZoneNotFoundError
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.presentation.api.routers.parking import router


def _build_test_app(use_case_mock: MagicMock) -> FastAPI:
    """Build a minimal FastAPI app with the parking router and a mocked use case."""
    app = FastAPI()
    app.include_router(router)
    app.state.find_nearest_ser_zone = use_case_mock
    return app


def _make_ser_zone(
    street_name: str = "Calle Mayor",
    zone_type: str = "Azul",
    spot_count: int = 15,
    lat: float = 40.4168,
    lng: float = -3.7038,
) -> SerZone:
    return SerZone(
        street_name=street_name,
        zone_type=zone_type,
        spot_count=spot_count,
        location=GeoLocation(lat=lat, lng=lng),
    )


def test_valid_coords_returns_200_with_correct_json() -> None:
    use_case = MagicMock()
    use_case.execute.return_value = _make_ser_zone()
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 200
    data = response.json()
    assert data["street_name"] == "Calle Mayor"
    assert data["zone_type"] == "Azul"
    assert data["spot_count"] == 15
    assert isinstance(data["distance_meters"], int)
    assert isinstance(data["latitude"], float)
    assert isinstance(data["longitude"], float)


def test_response_has_no_zone_code_field() -> None:
    use_case = MagicMock()
    use_case.execute.return_value = _make_ser_zone()
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 200
    assert "zone_code" not in response.json()


def test_response_has_no_zone_label_field() -> None:
    use_case = MagicMock()
    use_case.execute.return_value = _make_ser_zone()
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 200
    assert "zone_label" not in response.json()


def test_spot_count_minus_one_for_unknown_zone() -> None:
    use_case = MagicMock()
    use_case.execute.return_value = _make_ser_zone(spot_count=-1)
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 200
    assert response.json()["spot_count"] == -1


def test_empty_db_returns_404() -> None:
    use_case = MagicMock()
    use_case.execute.side_effect = SerZoneNotFoundError("No zone found")
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 404
    assert "No SER zone data available" in response.json()["detail"]


def test_missing_lat_param_returns_422() -> None:
    use_case = MagicMock()
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lng": -3.7038})

    assert response.status_code == 422


def test_missing_lng_param_returns_422() -> None:
    use_case = MagicMock()
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168})

    assert response.status_code == 422


def test_lat_out_of_range_returns_422() -> None:
    use_case = MagicMock()
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 999, "lng": -3.7038})

    assert response.status_code == 422


def test_lng_out_of_range_returns_422() -> None:
    use_case = MagicMock()
    client = TestClient(_build_test_app(use_case))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": 999})

    assert response.status_code == 422
