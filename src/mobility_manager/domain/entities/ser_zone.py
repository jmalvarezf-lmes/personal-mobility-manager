"""
Domain entity: SerZone.

Represents a SER (Servicio de Estacionamiento Regulado) bureaucratic parking
zone with a real polygon boundary. zone_type carries the city-specific zone
classification (e.g. "Azul", "Verde") as a validated display name.

SerZone does NOT carry street names — a zone can span many streets, and this
entity backs both the bulk zone-list query (used for map rendering, every
zone at once) and the single-coordinate lookup. Street names are fetched
separately, on demand, via SerZoneRepository.get_street_names() — see
design.md D9.

city_code identifies which city's enforcement schedule and holiday calendar
apply to this zone — see the ser-enforcement-schedule and
public-holiday-calendar capabilities of add-ser-enforcement-calendar.
"""

from dataclasses import dataclass

from pyproj import Transformer
from shapely.geometry import Point
from shapely.geometry.base import BaseGeometry

from mobility_manager.domain.value_objects.location import GeoLocation

# Reproject WGS84 EPSG:4326 -> UTM EPSG:25830, matching the geometry's storage CRS.
_wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)


@dataclass(frozen=True)
class SerZone:
    """Immutable SER zone entity with a real polygon boundary."""

    city_code: str  # identifies which city's enforcement schedule/holiday calendar applies
    zone_number: str
    zone_type: str  # validated display_name from the city's ZoneType
    district: str
    spot_count: int  # -1 means unknown
    geometry: BaseGeometry  # Polygon or MultiPolygon, EPSG:25830 metres

    def contains(self, location: GeoLocation, tolerance_m: float = 0.0) -> bool:
        """
        Return True if the given location falls within this zone's boundary,
        or within tolerance_m metres of its edge.

        Boundary-inclusive: a point exactly on the polygon's edge counts as
        contained (uses shapely's covers(), not the boundary-exclusive
        contains()). tolerance_m defaults to 0.0, which preserves the exact
        zero-tolerance boundary-inclusive behavior for any caller that
        doesn't pass a tolerance — it compensates for GPS positioning error
        when the caller opts in (see add-ser-zone-containment-tolerance
        design.md D2).
        """
        utm_x, utm_y = _wgs84_to_utm.transform(location.lng, location.lat)
        point = Point(utm_x, utm_y)
        return bool(self.geometry.covers(point) or self.geometry.distance(point) <= tolerance_m)
