"""
Application use case: CreateSerTicket.

Orchestrates SER ticket creation for a user's vehicle: verifies ownership,
loads the user's stored provider session, resolves the provider instance,
resolves the location (explicit override or the vehicle's latest known
location), calls create_ticket, and persists the result. Exposed over HTTP
via POST /parking/ser-tickets.
"""

import logging
import time
from dataclasses import replace
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
    SerTicketPersistenceError,
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

# Bounded retry for `_ticket_repo.save(ticket)` below, after the provider has
# already created (and charged) the real ticket (see this fix's docstring
# note on SerTicketPersistenceError). Deliberately NOT a full fix for
# extended outages — a DB outage long enough to defeat a handful of quick
# retries already breaks much more of this app than just this save — this
# only closes the realistic transient-failure window (query timeout,
# deadlock, momentary connection blip). Internal technical constants, not
# per-deployment tuning knobs — mirrors `_MAX_FUTURE_SECONDS` in
# record_vehicle_location.py.
_TICKET_SAVE_MAX_ATTEMPTS = 3
_TICKET_SAVE_RETRY_DELAY_SECONDS = 0.2


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
        auto_created: bool = False,
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
            auto_created: Whether this ticket was created automatically by
                SerTicketCreationTriggerHandler (True) or via the manual
                POST /parking/ser-tickets endpoint (False, the default — see
                add-ser-ticket-history-ui design.md D2). Persisted verbatim
                onto the returned ParkingTicket's `auto_created` field.

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
            SerTicketPersistenceError: If the provider already created (and
                charged) the real ticket, but persisting our own
                ParkingTicket record afterwards still fails after a bounded
                retry (`_TICKET_SAVE_MAX_ATTEMPTS` attempts,
                `_TICKET_SAVE_RETRY_DELAY_SECONDS` apart) — this is the one
                exception this use case itself raises (rather than
                propagating unmodified), because only this use case knows
                that specific case occurred (see design.md's "CreateSerTicket
                stays untouched" decision and its documented exception, this
                fix).
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

        # The provider itself never sets latitude/longitude/auto_created (it
        # doesn't know about creation provenance) — this is the single place
        # that fills them in with real values before persisting, for every
        # ticket created going forward (see add-ser-ticket-history-ui
        # design.md D3).
        ticket = replace(
            ticket,
            latitude=resolved_location.lat,
            longitude=resolved_location.lng,
            auto_created=auto_created,
        )

        # The provider has already created (and charged) the real ticket by
        # this point — a save failure here would otherwise mean we lose our
        # own record of a transaction that already happened on the
        # provider's side. Bounded retry closes the realistic transient
        # window (query timeout, deadlock, momentary connection blip)
        # before giving up (see this fix's docstring note above and
        # SerTicketPersistenceError's docstring).
        save_exc: Exception | None = None
        for attempt in range(1, _TICKET_SAVE_MAX_ATTEMPTS + 1):
            try:
                self._ticket_repo.save(ticket)
                save_exc = None
                break
            except Exception as exc:
                save_exc = exc
                logger.warning(
                    "Attempt %s/%s to persist ParkingTicket failed: vehicle_id=%s user_id=%s provider=%s",
                    attempt,
                    _TICKET_SAVE_MAX_ATTEMPTS,
                    vehicle_id,
                    user_id,
                    provider,
                )
                if attempt < _TICKET_SAVE_MAX_ATTEMPTS:
                    time.sleep(_TICKET_SAVE_RETRY_DELAY_SECONDS)

        if save_exc is not None:
            # Log everything needed for a manual reconciliation against the
            # provider's own records (mirrors register_vehicle.py's pattern
            # of logging around a post-critical-write side effect, applied
            # here to a higher-stakes real-money case). Raised as
            # SerTicketPersistenceError (rather than a bare `raise`) so
            # callers can distinguish "charged but unpersisted" from any
            # other creation failure (see this fix's docstring note above).
            logger.exception(
                "Failed to persist ParkingTicket after provider already created it, "
                "after %s attempts: vehicle_id=%s user_id=%s provider=%s provider_reference=%s cost=%s end_date=%s",
                _TICKET_SAVE_MAX_ATTEMPTS,
                vehicle_id,
                user_id,
                provider,
                ticket.provider_reference,
                ticket.cost,
                ticket.end_date,
                exc_info=save_exc,
            )
            raise SerTicketPersistenceError(
                f"Failed to persist ParkingTicket after provider already created it: vehicle_id={vehicle_id}"
            ) from save_exc

        return ticket
