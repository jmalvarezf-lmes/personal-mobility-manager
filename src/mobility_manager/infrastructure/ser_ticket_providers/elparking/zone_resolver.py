"""
Infrastructure-internal: ElParking town/zone/rate resolution algorithm.

Implements design.md decision 3:
  town: match City.name case-insensitively against cached/fetched ElParking
    town names.
  zone: match zone_number (zero-padded to 3 digits) against each cached
    zone's name-leading-number; when multiple candidates share a
    zone_number, disambiguate via shapely point-in-polygon against each
    candidate's own polygon_wkt, reprojected WGS84->UTM the same way
    SerZone.contains() already does.
  rate: match zone_type (stripped of a "Tarifa " prefix, case/accent-
    insensitive) against the resolved zone's cached rate names.

Kept entirely inside this package — never imported by domain/application code.
"""

import re
import unicodedata
from typing import Any

from shapely import wkt as shapely_wkt
from shapely.geometry import Point
from shapely.ops import transform

from mobility_manager.domain.value_objects.location import GeoLocation, _wgs84_to_utm
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
    ElParkingRate,
    ElParkingZone,
)

_ZONE_NAME_LEADING_NUMBER = re.compile(r"^\s*(\d+)")
_RATE_PREFIX = "tarifa "


def _normalize(text: str) -> str:
    """Case/accent-insensitive normalisation shared by town/rate matching."""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return without_accents.strip().lower()


def resolve_town_id(city_name: str, towns: list[dict[str, Any]]) -> str | None:
    """Match `city_name` case-insensitively against ElParking's town list; return its `id`, or None."""
    normalized_city = _normalize(city_name)
    for town in towns:
        if _normalize(town["name"]) == normalized_city:
            return str(town["id"])
    return None


def resolve_zone(zone_number: str, location: GeoLocation, zones: list[ElParkingZone]) -> ElParkingZone | None:
    """
    Match `zone_number` (zero-padded to 3 digits) against each zone's
    leading name number; disambiguate multiple matches via polygon
    containment against `location`.
    """
    padded = zone_number.zfill(3)
    candidates = []
    for zone in zones:
        match = _ZONE_NAME_LEADING_NUMBER.match(zone.name)
        if match and match.group(1).zfill(3) == padded:
            candidates.append(zone)

    if not candidates:
        return None
    if len(candidates) == 1:
        return candidates[0]

    utm_x, utm_y = _wgs84_to_utm.transform(location.lng, location.lat)
    point = Point(utm_x, utm_y)
    for zone in candidates:
        geometry = shapely_wkt.loads(zone.polygon_wkt)
        utm_geometry = transform(lambda x, y, z=None: _wgs84_to_utm.transform(x, y), geometry)
        if utm_geometry.covers(point):
            return zone
    return None


def resolve_rate(zone_type: str, rates: list[ElParkingRate]) -> ElParkingRate | None:
    """Match `zone_type` (stripped "Tarifa " prefix, case/accent-insensitive) against `rates`."""
    normalized_zone_type = _normalize(zone_type)
    for rate in rates:
        normalized_rate_name = _normalize(rate.name)
        if normalized_rate_name.startswith(_RATE_PREFIX):
            normalized_rate_name = normalized_rate_name[len(_RATE_PREFIX) :]
        if normalized_rate_name == normalized_zone_type:
            return rate
    return None
