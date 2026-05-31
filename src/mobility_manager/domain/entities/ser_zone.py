"""
Domain entity: SerZone.

Represents a Madrid SER (Servicio de Estacionamiento Regulado) parking zone
associated with a street segment.
"""
from dataclasses import dataclass

from mobility_manager.domain.value_objects.location import GeoLocation


@dataclass(frozen=True)
class SerZone:
    """Immutable SER zone entity."""

    street_name: str
    zone_code: str
    zone_label: str
    location: GeoLocation
