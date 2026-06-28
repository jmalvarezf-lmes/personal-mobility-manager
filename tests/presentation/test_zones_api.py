"""
Presentation tests for GET /parking/ser-zones endpoint.
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.presentation.api.routers.zones import router


def _build_app(repo_mock: MagicMock) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.ser_zone_repo = repo_mock
    return app


def _make_zone(
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
    assert zone["street_name"] == "Calle Mayor"
    assert zone["zone_type"] == "Azul"
    assert zone["colour"] == "#2563EB"
    assert zone["spot_count"] == 15
    assert zone["lat"] == 40.4168
    assert zone["lng"] == -3.7038


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


def test_list_zones_alta_rotacion_has_grey_colour() -> None:
    repo = MagicMock()
    repo.list_all.return_value = [_make_zone(zone_type="Alta Rotación")]
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#6B7280"


def test_unknown_city_returns_404() -> None:
    repo = MagicMock()
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "barcelona"})

    assert response.status_code == 404
    assert "barcelona" in response.json()["detail"]
