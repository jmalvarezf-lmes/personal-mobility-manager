"""
Presentation tests for GET /parking/ser-zones endpoint.
"""

from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from shapely.geometry import Polygon

from mobility_manager.domain.entities.city import City
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.value_objects.zone_area import ZoneArea
from mobility_manager.presentation.api.routers.zones import router

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


def _build_app(repo_mock: MagicMock, city_repo_mock: MagicMock | None = None) -> FastAPI:
    app = FastAPI()
    app.include_router(router)
    app.state.ser_zone_repo = repo_mock
    app.state.city_repo = city_repo_mock if city_repo_mock is not None else _make_city_repo()
    return app


def _make_city_repo(codes: list[str] | None = None) -> MagicMock:
    """Build a city_repo mock; defaults to a single 'madrid' row."""
    repo = MagicMock()
    codes = codes if codes is not None else ["madrid"]
    repo.list_all.return_value = [City(code=c, name=c.capitalize()) for c in codes]
    return repo


def _make_repo(zones: list[SerZone] | None = None, zone_areas: list[ZoneArea] | None = None) -> MagicMock:
    """Build a repo mock with sane empty-list defaults for list_zones_for_city/list_zone_areas_for_city."""
    repo = MagicMock()
    repo.list_zones_for_city.return_value = zones if zones is not None else []
    repo.list_zone_areas_for_city.return_value = zone_areas if zone_areas is not None else []
    return repo


def _make_zone(
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


def _make_zone_area(
    zone_number: str = "163",
    neighbourhood: str = "Sol",
    geometry: Polygon = _SQUARE,
) -> ZoneArea:
    return ZoneArea(city_code="madrid", zone_number=zone_number, neighbourhood=neighbourhood, geometry=geometry)


def test_list_zones_empty_returns_200_with_empty_list() -> None:
    repo = _make_repo()
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "madrid"
    assert data["zones"] == []
    assert data["frontiers"] == []


def test_list_zones_returns_correct_fields() -> None:
    repo = _make_repo(zones=[_make_zone()])
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
    repo = _make_repo(zones=[_make_zone()])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    geometry = response.json()["zones"][0]["geometry"]
    lng, lat = geometry["coordinates"][0][0]
    # WGS84 Madrid bbox sanity check — UTM 25830 coordinates would fail this.
    assert 40.0 <= lat <= 41.0
    assert -4.0 <= lng <= -3.0


def test_list_zones_azul_has_blue_colour() -> None:
    repo = _make_repo(zones=[_make_zone(zone_type="Azul")])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#2563EB"


def test_list_zones_verde_has_green_colour() -> None:
    repo = _make_repo(zones=[_make_zone(zone_type="Verde")])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#16A34A"


def test_list_zones_alta_rotacion_has_purple_colour() -> None:
    repo = _make_repo(zones=[_make_zone(zone_type="Alta Rotación")])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#7C3AED"


def test_list_zones_naranja_has_orange_colour() -> None:
    repo = _make_repo(zones=[_make_zone(zone_type="Naranja")])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#F97316"


def test_list_zones_rojo_has_red_colour() -> None:
    repo = _make_repo(zones=[_make_zone(zone_type="Rojo")])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.json()["zones"][0]["colour"] == "#DC2626"


def test_unknown_city_returns_404() -> None:
    """A city absent from the live `cities` table returns 404, not a hardcoded set check."""
    repo = _make_repo()
    city_repo = _make_city_repo(codes=["madrid"])
    client = TestClient(_build_app(repo, city_repo))

    response = client.get("/parking/ser-zones", params={"city": "barcelona"})

    assert response.status_code == 404
    assert "barcelona" in response.json()["detail"]


def test_newly_seeded_city_becomes_queryable_without_a_code_change() -> None:
    """A city row added to `cities` (even one with no zones yet) must be queryable — no hardcoded set."""
    repo = _make_repo()
    city_repo = _make_city_repo(codes=["madrid", "barcelona"])
    client = TestClient(_build_app(repo, city_repo))

    response = client.get("/parking/ser-zones", params={"city": "barcelona"})

    assert response.status_code == 200
    assert response.json()["city"] == "barcelona"


def test_zones_are_fetched_via_city_scoped_repository_methods() -> None:
    """The endpoint must call list_zones_for_city/list_zone_areas_for_city, not the unscoped list_all/list_zone_areas."""
    repo = _make_repo()
    client = TestClient(_build_app(repo))

    client.get("/parking/ser-zones", params={"city": "madrid"})

    repo.list_zones_for_city.assert_called_once_with("madrid")
    repo.list_zone_areas_for_city.assert_called_once_with("madrid")
    repo.list_all.assert_not_called()
    repo.list_zone_areas.assert_not_called()


# ---------------------------------------------------------------------------
# frontiers array
# ---------------------------------------------------------------------------


def test_frontiers_array_has_correct_fields() -> None:
    repo = _make_repo(zone_areas=[_make_zone_area()])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    assert response.status_code == 200
    frontier = response.json()["frontiers"][0]
    assert frontier["zone_number"] == "163"
    assert frontier["neighbourhood"] == "Sol"
    assert frontier["geometry"]["type"] == "Polygon"
    assert "colour" not in frontier
    assert "zone_type" not in frontier
    assert "street_names" not in frontier


def test_frontiers_geometry_is_reprojected_to_wgs84() -> None:
    repo = _make_repo(zone_areas=[_make_zone_area()])
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    geometry = response.json()["frontiers"][0]["geometry"]
    lng, lat = geometry["coordinates"][0][0]
    assert 40.0 <= lat <= 41.0
    assert -4.0 <= lng <= -3.0


def test_frontiers_array_has_one_entry_per_zone_number_not_per_zone_type() -> None:
    """A zone_number with three `zones` entries (colours) still has one frontiers entry."""
    repo = _make_repo(
        zones=[
            _make_zone(zone_number="163", zone_type="Azul"),
            _make_zone(zone_number="163", zone_type="Verde"),
            _make_zone(zone_number="163", zone_type="Alta Rotación"),
        ],
        zone_areas=[_make_zone_area(zone_number="163")],
    )
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    data = response.json()
    assert len(data["zones"]) == 3
    assert len(data["frontiers"]) == 1


def test_two_zone_numbers_sharing_barrio_return_identical_frontier_geometry() -> None:
    repo = _make_repo(
        zone_areas=[
            _make_zone_area(zone_number="163", neighbourhood="Sol"),
            _make_zone_area(zone_number="200", neighbourhood="Sol"),
        ]
    )
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zones", params={"city": "madrid"})

    frontiers = response.json()["frontiers"]
    assert len(frontiers) == 2
    assert {f["zone_number"] for f in frontiers} == {"163", "200"}
    assert frontiers[0]["geometry"] == frontiers[1]["geometry"]


# ---------------------------------------------------------------------------
# GET /parking/ser-zone-options — lightweight zone_number/neighbourhood pairs
# ---------------------------------------------------------------------------


def test_zone_options_empty_city_returns_200_with_empty_list() -> None:
    repo = _make_repo()
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zone-options", params={"city": "madrid"})

    assert response.status_code == 200
    data = response.json()
    assert data["city"] == "madrid"
    assert data["options"] == []


def test_zone_options_populated_city_returns_zone_number_and_neighbourhood_only() -> None:
    repo = _make_repo(
        zone_areas=[
            _make_zone_area(zone_number="163", neighbourhood="Sol"),
            _make_zone_area(zone_number="200", neighbourhood="Malasaña"),
        ]
    )
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zone-options", params={"city": "madrid"})

    assert response.status_code == 200
    options = response.json()["options"]
    assert len(options) == 2
    assert {(o["zone_number"], o["neighbourhood"]) for o in options} == {
        ("163", "Sol"),
        ("200", "Malasaña"),
    }
    assert set(options[0].keys()) == {"zone_number", "neighbourhood"}


def test_zone_options_unknown_city_returns_404() -> None:
    repo = _make_repo()
    city_repo = _make_city_repo(codes=["madrid"])
    client = TestClient(_build_app(repo, city_repo))

    response = client.get("/parking/ser-zone-options", params={"city": "barcelona"})

    assert response.status_code == 404
    assert "barcelona" in response.json()["detail"]


def test_zone_options_uses_city_scoped_repository_method() -> None:
    """Must call list_zone_areas_for_city, not the unscoped list_zone_areas — no geometry work either."""
    repo = _make_repo()
    client = TestClient(_build_app(repo))

    client.get("/parking/ser-zone-options", params={"city": "madrid"})

    repo.list_zone_areas_for_city.assert_called_once_with("madrid")
    repo.list_zone_areas.assert_not_called()
    repo.list_zones_for_city.assert_not_called()


def test_zone_options_does_not_leak_across_cities() -> None:
    """Seeding two cities' worth of data proves no cross-city leakage, same isolation pattern as ser-zones."""

    def _list_zone_areas_for_city(city_code: str) -> list[ZoneArea]:
        by_city = {
            "madrid": [_make_zone_area(zone_number="163", neighbourhood="Sol")],
            "valencia": [_make_zone_area(zone_number="900", neighbourhood="Ruzafa")],
        }
        return by_city.get(city_code, [])

    repo = _make_repo()
    repo.list_zone_areas_for_city.side_effect = _list_zone_areas_for_city
    city_repo = _make_city_repo(codes=["madrid", "valencia"])
    client = TestClient(_build_app(repo, city_repo))

    response = client.get("/parking/ser-zone-options", params={"city": "madrid"})

    assert response.status_code == 200
    options = response.json()["options"]
    assert len(options) == 1
    assert options[0]["neighbourhood"] == "Sol"


# ---------------------------------------------------------------------------
# GET /parking/ser-zone-options — sort param
# ---------------------------------------------------------------------------


def _make_unsorted_zone_areas() -> list[ZoneArea]:
    """zone_number order (as the repository/SQL returns it) is deliberately not alphabetical
    by neighbourhood, so ordering assertions actually distinguish sort=asc/desc from the
    underlying zone_number ordering."""
    return [
        _make_zone_area(zone_number="163", neighbourhood="Sol"),
        _make_zone_area(zone_number="011", neighbourhood="Palacio"),
        _make_zone_area(zone_number="200", neighbourhood="Malasaña"),
    ]


def test_zone_options_default_sort_is_ascending_by_neighbourhood() -> None:
    repo = _make_repo(zone_areas=_make_unsorted_zone_areas())
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zone-options", params={"city": "madrid"})

    assert response.status_code == 200
    neighbourhoods = [o["neighbourhood"] for o in response.json()["options"]]
    assert neighbourhoods == ["Malasaña", "Palacio", "Sol"]


def test_zone_options_explicit_sort_asc_returns_ascending() -> None:
    repo = _make_repo(zone_areas=_make_unsorted_zone_areas())
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zone-options", params={"city": "madrid", "sort": "asc"})

    assert response.status_code == 200
    neighbourhoods = [o["neighbourhood"] for o in response.json()["options"]]
    assert neighbourhoods == ["Malasaña", "Palacio", "Sol"]


def test_zone_options_sort_desc_returns_descending() -> None:
    repo = _make_repo(zone_areas=_make_unsorted_zone_areas())
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zone-options", params={"city": "madrid", "sort": "desc"})

    assert response.status_code == 200
    neighbourhoods = [o["neighbourhood"] for o in response.json()["options"]]
    assert neighbourhoods == ["Sol", "Palacio", "Malasaña"]


def test_zone_options_invalid_sort_value_returns_422() -> None:
    repo = _make_repo(zone_areas=_make_unsorted_zone_areas())
    client = TestClient(_build_app(repo))

    response = client.get("/parking/ser-zone-options", params={"city": "madrid", "sort": "sideways"})

    assert response.status_code == 422
