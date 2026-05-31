"""
Infrastructure adapter: MadridSerService.

Implements ParkingServicePort for Madrid's Servicio de Estacionamiento Regulado (SER).
Add other cities as sibling directories under parking_services/.
"""
from mobility_manager.domain.ports.parking_service import ParkingServicePort


class MadridSerService(ParkingServicePort):
    """Interacts with Madrid's SER parking system."""

    pass
