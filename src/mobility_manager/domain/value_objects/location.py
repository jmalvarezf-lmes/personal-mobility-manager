"""
Value object: GeoLocation.

Immutable geographic coordinate pair (latitude, longitude).
"""

from dataclasses import dataclass


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
