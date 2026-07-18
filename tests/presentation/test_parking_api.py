"""
Presentation tests for GET /parking/ser-zone endpoint.

Uses FastAPI TestClient with mocked use case + repo via app.state.
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.exceptions import SerZoneNotFoundError
from mobility_manager.domain.value_objects.zone_area import ZoneArea
from mobility_manager.presentation.api.routers.parking import router

# Square centred close to (lat=40.4168, lng=-3.7038) in EPSG:25830.
_SQUARE = Polygon([(440280, 4474247), (440300, 4474247), (440300, 4474267), (440280, 4474267)])


def _build_test_app(use_case_mock: MagicMock, repo_mock: MagicMock | None = None) -> FastAPI:
    """Build a minimal FastAPI app with the parking router and mocked collaborators."""
    app = FastAPI()
    app.include_router(router)
    app.state.find_nearest_ser_zone = use_case_mock
    app.state.ser_zone_repo = (
        repo_mock
        if repo_mock is not None
        else MagicMock(get_street_names=lambda *a: [], get_zone_area=lambda *a: None)
    )
    return app


def _make_ser_zone(
    zone_number: str = "163",
    zone_type: str = "Azul",
    district: str = "CENTRO",
    spot_count: int = 15,
    geometry: Polygon = _SQUARE,
) -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number=zone_number,
        zone_type=zone_type,
        district=district,
        spot_count=spot_count,
        geometry=geometry,
    )


def test_valid_coords_returns_200_with_correct_json() -> None:
    use_case = MagicMock()
    use_case.execute.return_value = _make_ser_zone()
    repo = MagicMock()
    repo.get_street_names.return_value = ["ABADA", "GRAN VIA"]
    repo.get_zone_area.return_value = ZoneArea(
        city_code="madrid", zone_number="163", neighbourhood="Sol", geometry=_SQUARE
    )
    client = TestClient(_build_test_app(use_case, repo))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 200
    data = response.json()
    assert data["zone_number"] == "163"
    assert data["zone_type"] == "Azul"
    assert data["district"] == "CENTRO"
    assert data["neighbourhood"] == "Sol"
    assert data["street_names"] == ["ABADA", "GRAN VIA"]
    assert data["spot_count"] == 15
    assert isinstance(data["distance_meters"], int)
    repo.get_street_names.assert_called_once_with("madrid", "163", "Azul")
    repo.get_zone_area.assert_called_once_with("madrid", "163")


def test_neighbourhood_is_null_when_no_zone_area_row_exists() -> None:
    use_case = MagicMock()
    use_case.execute.return_value = _make_ser_zone()
    repo = MagicMock()
    repo.get_street_names.return_value = []
    repo.get_zone_area.return_value = None
    client = TestClient(_build_test_app(use_case, repo))

    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 200
    assert response.json()["neighbourhood"] is None


def test_point_inside_zone_returns_zero_distance() -> None:
    use_case = MagicMock()
    use_case.execute.return_value = _make_ser_zone()
    repo = MagicMock()
    repo.get_street_names.return_value = []
    repo.get_zone_area.return_value = None
    client = TestClient(_build_test_app(use_case, repo))

    # Centre of the square, which corresponds to roughly (40.4168, -3.7038).
    response = client.get("/parking/ser-zone", params={"lat": 40.4168, "lng": -3.7038})

    assert response.status_code == 200
    assert response.json()["distance_meters"] == 0


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
