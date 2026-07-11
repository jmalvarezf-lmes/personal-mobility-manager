"""
Presentation tests for GET /parking/ser-zones endpoint.
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.presentation.api.routers.zones import router

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


def _build_app(repo_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.ser_zone_repo = repo_mock
    return app


def _make_zone(
    zone_number: str = "163",
    zone_type: str = "Azul",
    district: str = "CENTRO",
    spot_count: int = 15,
    geometry: Polygon = _SQUARE,
) -> SerZone:
    return SerZone(
        zone_number=zone_number,
        zone_type=zone_type,
        district=district,
        spot_count=spot_count,
        geometry=geometry,
    )


def test_list_zones_empty_returns_200_with_empty_list() -> None:
    repo = MagicMock()
    repo.list_all.return_value = []
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "madrid"
    assert data["zones"] == []


def test_list_zones_returns_correct_fields() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone()]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.status_code == 200
    zone = response.json()["zones"][0]
    assert zone["zone_number"] == "163"
    assert zone["zone_type"] == "Azul"
    assert zone["colour"] == "#2563EB"
    assert zone["district"] == "CENTRO"
    assert zone["spot_count"] == 15
    assert zone["geometry"]["type"] == "Polygon"
    assert "street_names" not in zone


def test_list_zones_geometry_is_reprojected_to_wgs84() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone()]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    geometry = response.json()["zones"][0]["geometry"]
    lng, lat = geometry["coordinates"][0][0]
    # WGS84 Madrid bbox sanity check — UTM 25830 coordinates would fail this.
    assert 40.0 <= lat <= 41.0
    assert -4.0 <= lng <= -3.0


def test_list_zones_azul_has_blue_colour() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone(zone_type="Azul")]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#2563EB"


def test_list_zones_verde_has_green_colour() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone(zone_type="Verde")]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#16A34A"


def test_list_zones_alta_rotacion_has_purple_colour() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone(zone_type="Alta Rotación")]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#7C3AED"


def test_list_zones_naranja_has_orange_colour() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone(zone_type="Naranja")]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#F97316"


def test_list_zones_rojo_has_red_colour() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone(zone_type="Rojo")]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#DC2626"


def test_unknown_city_returns_404() -> None:
    repo = MagicMock()
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "barcelona"})

    assert response.status_code == 404
    assert "barcelona" in response.json()["detail"]
