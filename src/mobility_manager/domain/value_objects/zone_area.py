"""
Domain: ZoneArea value object.

Query-time read model carrying a zone_number's presentation-only "frontier"
— a real Madrid Barrios administrative boundary polygon and its official
neighbourhood name. Distinct from SerZone: ZoneArea exists at zone_number
grain (not (zone_number, zone_type) grain) and carries no zone_type,
spot_count, or containment behaviour — see add-ser-zone-frontiers design.md
D6/D8.
"""

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class ZoneArea:
    """Immutable frontier value object: one real barrio boundary per zone_number."""

    zone_number: str
    neighbourhood: str
    geometry: BaseGeometry  # Polygon or MultiPolygon, EPSG:25830 metres
