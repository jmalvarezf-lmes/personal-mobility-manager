"""
Application use case: CreateSerTicket.

Orchestrates SER ticket creation for a user's vehicle: verifies ownership,
loads the user's stored provider session, resolves the provider instance,
calls create_ticket, and persists the result. Not exposed over HTTP in this
change — exercised only by unit tests against a fake SerTicketProviderPort.
"""

from uuid import UUID

from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.exceptions import (
    SerProviderSessionNotFoundError,
    SerTicketProviderNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.ports.user_ser_provider_config_repository import (
    UserSerProviderConfigRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository


class CreateSerTicket:
    """Create a SER parking ticket for a vehicle owned by a user."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        config_repo: UserSerProviderConfigRepository,
        ticket_repo: ParkingTicketRepository,
        providers: dict[str, SerTicketProviderPort],
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._config_repo = config_repo
        self._ticket_repo = ticket_repo
        self._providers = providers

    def execute(self, user_id: UUID, vehicle_id: UUID, provider: str, duration_minutes: int) -> ParkingTicket:
        """
        Create and persist a SER parking ticket.

        Args:
            user_id: The requesting user.
            vehicle_id: The vehicle to create a ticket for.
            provider: The SER provider name to use.
            duration_minutes: Requested ticket duration in minutes.

        Returns:
            The persisted ParkingTicket.

        Raises:
            VehicleNotFoundError: If the vehicle doesn't exist, or exists but isn't
                owned by user_id — deliberately indistinguishable to avoid leaking
                ownership information.
            SerProviderSessionNotFoundError: If no stored session exists for
                (user_id, provider).
            SerTicketProviderNotFoundError: If `provider` is not registered.
        """
        vehicle = self._vehicle_repo.find_by_id(vehicle_id)
        if vehicle is None or vehicle.user_id != user_id:
            raise VehicleNotFoundError(f"No vehicle found for id {vehicle_id}")

        session = self._config_repo.find(user_id, provider)
        if session is None:
            raise SerProviderSessionNotFoundError(f"No stored session for user {user_id} and provider {provider!r}")

        provider_instance = self._providers.get(provider)
        if provider_instance is None:
            raise SerTicketProviderNotFoundError(f"No SER ticket provider registered for {provider!r}")

        ticket = provider_instance.create_ticket(session, vehicle, duration_minutes)
        self._ticket_repo.save(ticket)
        return ticket
