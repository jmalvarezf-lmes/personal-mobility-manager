"""
Value object: GeoLocation.

Immutable geographic coordinate pair (latitude, longitude). Also hosts
distance_m, a pure geo-math helper with no SQL/repo dependency of its own —
originally lived in infrastructure/repositories/postgres/ser_zone_repo.py,
but the notification-dispatch handler (application layer) needs it too, and
importing a pure function from a Postgres-specific infrastructure module
into the application layer would be a layering violation.
"""

import math
from dataclasses import dataclass

from pyproj import Transformer

# WGS84 → EPSG:25830; always_xy=True means transform(lng, lat) → (easting, northing)
_wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)


@dataclass(frozen=True)
class GeoLocation:
    """Immutable geographic location value object."""

    lat: float
    lng: float

    def __post_init__(self) -> None:
        if not (-90 <= self.lat <= 90):
            raise ValueError(f"Latitude must be between -90 and 90, got {self.lat}")
        if not (-180 <= self.lng <= 180):
            raise ValueError(f"Longitude must be between -180 and 180, got {self.lng}")


def distance_m(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Euclidean distance in metres between two WGS84 points via UTM Zone 30N."""
    x1, y1 = _wgs84_to_utm.transform(lng1, lat1)
    x2, y2 = _wgs84_to_utm.transform(lng2, lat2)
    return math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
