"""
Unit tests for the ElParking town/zone/rate resolution helpers (zone_resolver.py).
"""

from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
    ElParkingRate,
    ElParkingZone,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_resolver import (
    resolve_rate,
    resolve_town_id,
    resolve_zone,
)

_SQUARE_A = "POLYGON((-3.70 40.40, -3.699 40.40, -3.699 40.401, -3.70 40.401, -3.70 40.40))"
_SQUARE_B = "POLYGON((-3.60 40.30, -3.599 40.30, -3.599 40.301, -3.60 40.301, -3.60 40.30))"
_SQUARE_C = "POLYGON((-3.50 40.20, -3.499 40.20, -3.499 40.201, -3.50 40.201, -3.50 40.20))"

_INSIDE_A = GeoLocation(lat=40.4005, lng=-3.6995)


def test_resolve_town_id_matches_case_and_accent_insensitively() -> None:
    towns = [{"id": "town-1", "name": "MADRID"}]

    assert resolve_town_id("madrid", towns) == "town-1"


def test_resolve_town_id_matches_accented_name_against_unaccented_town() -> None:
    towns = [{"id": "town-1", "name": "Alcala de Henares"}]

    assert resolve_town_id("Alcalá de Henares", towns) == "town-1"


def test_resolve_town_id_returns_none_when_no_match() -> None:
    towns = [{"id": "town-1", "name": "Madrid"}]

    assert resolve_town_id("Barcelona", towns) is None


def test_resolve_zone_returns_none_when_no_candidate_matches_zone_number() -> None:
    zones = [ElParkingZone(id="zone-1", name="12 - SOMEWHERE", polygon_wkt=_SQUARE_A, rates=[])]

    assert resolve_zone("999", _INSIDE_A, zones) is None


def test_resolve_zone_disambiguates_more_than_two_duplicate_candidates_by_polygon() -> None:
    zones = [
        ElParkingZone(id="zone-A", name="084 - ZONE A", polygon_wkt=_SQUARE_A, rates=[]),
        ElParkingZone(id="zone-B", name="084 - ZONE B", polygon_wkt=_SQUARE_B, rates=[]),
        ElParkingZone(id="zone-C", name="084 - ZONE C", polygon_wkt=_SQUARE_C, rates=[]),
    ]

    result = resolve_zone("084", _INSIDE_A, zones)

    assert result is not None
    assert result.id == "zone-A"


def test_resolve_zone_returns_none_when_no_duplicate_candidate_contains_location() -> None:
    zones = [
        ElParkingZone(id="zone-B", name="084 - ZONE B", polygon_wkt=_SQUARE_B, rates=[]),
        ElParkingZone(id="zone-C", name="084 - ZONE C", polygon_wkt=_SQUARE_C, rates=[]),
    ]

    # _INSIDE_A falls inside neither zone B's nor zone C's polygon.
    assert resolve_zone("084", _INSIDE_A, zones) is None


def test_resolve_rate_returns_none_when_no_rate_matches() -> None:
    rates = [ElParkingRate(id="rate-1", name="Tarifa Verde")]

    assert resolve_rate("Azul", rates) is None


def test_resolve_rate_matches_stripped_prefix_case_and_accent_insensitively() -> None:
    rates = [ElParkingRate(id="rate-1", name="TARIFA AZUL")]

    result = resolve_rate("azul", rates)

    assert result is not None
    assert result.id == "rate-1"
