"""
Domain: SerZoneBoundaryRecord value object.

Carries the parsed output from any CityParkingDataProvider once SerZone
became a bureaucratic zone with a real polygon boundary. Replaces the
point-based ParkingSpotRecord (see design.md D1).

This is an ingestion-time record only: street_names exists so the ingestion
use case can populate the separate ser_zone_streets table — it is not carried
on the query-time SerZone entity (see design.md D9).
"""

from dataclasses import dataclass

from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class SerZoneBoundaryRecord:
    """Immutable record of one dissolved SER zone boundary."""

    zone_number: str
    zone_type: str  # validated display_name from the city's ZoneType
    district: str
    street_names: list[str]
    spot_count: int  # -1 means unknown (source did not include spot count)
    geometry: BaseGeometry  # Polygon or MultiPolygon, EPSG:25830 metres
