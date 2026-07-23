"""
Infrastructure-internal dataclasses: ElParking zone-mapping cache shapes.

These represent one (city_code, provider) cache entry: the town's ElParking
id plus its fetched zones (id, name, polygon_wkt) and each zone's rates.
Kept entirely inside this package — their vocabulary (id_ser_town,
id_ser_zone/rate ids) is ElParking-specific and must never leak past
SerTicketProviderPort into domain or application code.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class ElParkingRate:
    """One rate entry under an ElParking zone (e.g. `{"id": ..., "name": "Tarifa Azul"}`)."""

    id: str
    name: str


@dataclass(frozen=True)
class ElParkingZone:
    """One ElParking SER zone within a town, with its own polygon and rates."""

    id: str
    name: str
    polygon_wkt: str
    rates: list[ElParkingRate] = field(default_factory=list)


@dataclass(frozen=True)
class ElParkingZoneMapping:
    """One cached (city_code, provider) entry: the resolved town id plus its zones."""

    id_ser_town: str
    zones: list[ElParkingZone]
    fetched_at: datetime
