"""
Domain entity: SerZone.

Represents a SER (Servicio de Estacionamiento Regulado) parking zone
associated with a street address. zone_type carries the city-specific
zone classification (e.g. "Azul", "Verde") as a validated display name.
"""

from dataclasses import dataclass

from mobility_manager.domain.value_objects.location import GeoLocation


@dataclass(frozen=True)
class SerZone:
    """Immutable SER zone entity."""

    street_name: str
    zone_type: str  # validated display_name from the city's ZoneType
    spot_count: int  # -1 means unknown
    location: GeoLocation
