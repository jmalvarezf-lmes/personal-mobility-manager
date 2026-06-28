"""
Domain: ParkingSpotRecord value object.

Carries the parsed output from any CityParkingDataProvider. Replaces the
infrastructure-scoped SerZoneRecord that was tied to the Madrid callejero CSV.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ParkingSpotRecord:
    """Immutable record of a single parking spot cluster at a street address."""

    street_name: str
    zone_type: str  # display_name from the city's ZoneType implementation
    latitude: float  # WGS84 — for bounding-box index
    longitude: float  # WGS84 — for bounding-box index
    utm_x: float  # EPSG:25830 easting (metres) — for Euclidean distance
    utm_y: float  # EPSG:25830 northing (metres) — for Euclidean distance
    spot_count: int  # -1 means unknown (source did not include spot count)
