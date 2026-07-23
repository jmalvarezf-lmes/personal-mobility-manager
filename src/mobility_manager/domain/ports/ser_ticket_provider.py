"""
Port (interface): SerTicketProviderPort.

Abstract contract that all SER ticket providers must implement. Login is a
mandatory, explicit step (unlike VehiclePullLocationPort's inline auth)
because SER provider accounts are user-scoped and produce a session that
must be persisted and reused across many ticket creations.

Note: `domain/ports/parking_service.py` is a separate, unrelated tombstone
stub and is intentionally left untouched by this port.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)


class SerTicketProviderPort(ABC):
    """Abstract SER ticket provider — implemented per city/operator in infrastructure."""

    @abstractmethod
    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        """Authenticate with the provider and return a session to reuse for ticket creation."""
        ...

    @abstractmethod
    def create_ticket(
        self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int, location: GeoLocation
    ) -> ParkingTicket:
        """
        Create a parking ticket for the given vehicle, at the given location,
        using a previously obtained session.

        `location` is always a resolved GeoLocation — the port itself never
        falls back to a stored or default location; that decision is made by
        the caller (see CreateSerTicket).

        Raises:
            SerProviderVehicleNotFoundError: `vehicle`'s license plate could
                not be matched against the provider's own vehicle records.
            SerProviderApiError: Any other provider-side failure.
        """
        ...

    @abstractmethod
    def logout(self, session: SerProviderSession) -> None:
        """
        Invalidate the given session on the provider's side.

        Raises:
            SerProviderApiError: The logout call failed (network error, unexpected status).
        """
        ...
