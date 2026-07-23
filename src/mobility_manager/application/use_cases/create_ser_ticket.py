"""
Application use case: CreateSerTicket.

Orchestrates SER ticket creation for a user's vehicle: verifies ownership,
loads the user's stored provider session, resolves the provider instance,
resolves the location (explicit override or the vehicle's latest known
location), calls create_ticket, and persists the result. Exposed over HTTP
via POST /parking/ser-tickets.
"""

import logging
from uuid import UUID

from mobility_manager.application.use_cases.get_latest_vehicle_location import (
    GetLatestVehicleLocation,
)
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.events.vehicle_not_present_in_ser_ticket_provider import (
    VehicleNotPresentInSerTicketProvider,
)
from mobility_manager.domain.exceptions import (
    SerProviderSessionNotFoundError,
    SerProviderVehicleNotFoundError,
    SerTicketProviderNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.ports.event_publisher import EventPublisher
from mobility_manager.domain.ports.parking_ticket_repository import (
    ParkingTicketRepository,
)
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.ports.user_ser_provider_config_repository import (
    UserSerProviderConfigRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.value_objects.location import GeoLocation

logger = logging.getLogger(__name__)


class CreateSerTicket:
    """Create a SER parking ticket for a vehicle owned by a user."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        config_repo: UserSerProviderConfigRepository,
        ticket_repo: ParkingTicketRepository,
        providers: dict[str, SerTicketProviderPort],
        event_publisher: EventPublisher,
        get_latest_vehicle_location: GetLatestVehicleLocation,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._config_repo = config_repo
        self._ticket_repo = ticket_repo
        self._providers = providers
        self._event_publisher = event_publisher
        self._get_latest_vehicle_location = get_latest_vehicle_location

    def execute(
        self,
        user_id: UUID,
        vehicle_id: UUID,
        provider: str,
        duration_minutes: int,
        location: GeoLocation | None = None,
    ) -> ParkingTicket:
        """
        Create and persist a SER parking ticket.

        Args:
            user_id: The requesting user.
            vehicle_id: The vehicle to create a ticket for.
            provider: The SER provider name to use.
            duration_minutes: Requested ticket duration in minutes.
            location: An explicit location override. When omitted, the
                vehicle's latest known location is resolved via
                GetLatestVehicleLocation before calling the provider.

        Returns:
            The persisted ParkingTicket.

        Raises:
            VehicleNotFoundError: If the vehicle doesn't exist, or exists but isn't
                owned by user_id — deliberately indistinguishable to avoid leaking
                ownership information.
            SerProviderSessionNotFoundError: If no stored session exists for
                (user_id, provider).
            SerTicketProviderNotFoundError: If `provider` is not registered.
            VehicleLocationNotFoundError: If `location` is omitted and the
                vehicle has no recorded location history.
            SerProviderVehicleNotFoundError: If the provider can't match the
                vehicle against its own vehicle records — re-raised after
                publishing VehicleNotPresentInSerTicketProvider.
            SerZoneNotFoundError: May propagate unmodified from the provider
                call when the resolved location doesn't fall inside any
                known SER zone.
            SerProviderApiError: May propagate unmodified from the provider
                call for any other provider-side or resolution failure.
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

        resolved_location = location
        if resolved_location is None:
            latest_location = self._get_latest_vehicle_location.execute(vehicle_id)
            resolved_location = GeoLocation(lat=latest_location.latitude, lng=latest_location.longitude)

        try:
            ticket = provider_instance.create_ticket(session, vehicle, duration_minutes, resolved_location)
        except SerProviderVehicleNotFoundError:
            self._event_publisher.publish(
                VehicleNotPresentInSerTicketProvider(vehicle_id=vehicle_id, user_id=user_id, provider=provider)
            )
            raise

        try:
            self._ticket_repo.save(ticket)
        except Exception:
            # The provider has already created (and charged) the real ticket
            # at this point — a failure here means we lose our own record of
            # a transaction that already happened on the provider's side.
            # Log everything needed for a manual reconciliation against the
            # provider's own records (mirrors register_vehicle.py's pattern
            # of logging around a post-critical-write side effect, applied
            # here to a higher-stakes real-money case).
            logger.exception(
                "Failed to persist ParkingTicket after provider already created it: "
                "vehicle_id=%s user_id=%s provider=%s provider_reference=%s cost=%s end_date=%s",
                vehicle_id,
                user_id,
                provider,
                ticket.provider_reference,
                ticket.cost,
                ticket.end_date,
            )
            raise

        return ticket
