"""
Domain: ZoneArea value object.

Query-time read model carrying a zone_number's presentation-only "frontier"
— a real Madrid Barrios administrative boundary polygon and its official
neighbourhood name. Distinct from SerZone: ZoneArea exists at
(city_code, zone_number) grain (not (zone_number, zone_type) grain) and
carries no zone_type, spot_count, or containment behaviour — see
add-ser-zone-frontiers design.md D6/D8.

city_code disambiguates zone_number values that may collide across cities
— see add-ser-enforcement-calendar design.md D5.
"""

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class ZoneArea:
    """Immutable frontier value object: one real barrio boundary per (city_code, zone_number)."""

    city_code: str
    zone_number: str
    neighbourhood: str
    geometry: BaseGeometry  # Polygon or MultiPolygon, EPSG:25830 metres
