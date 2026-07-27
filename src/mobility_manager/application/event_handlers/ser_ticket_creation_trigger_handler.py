"""
Application event handler: SerTicketCreationTriggerHandler.

Subscribed to VehicleLocationUpdated alongside SerTicketNotificationTriggerHandler
(see design.md decision 1) — active only when the vehicle owner's
`UserPreferences.auto_create_ticket` is `true`.

Gates on a *zone transition*, not raw movement distance (see
change-ser-auto-ticket-zone-gate design.md): a vehicle driving around inside
an already-covered SER zone should not repeatedly reach
`DetermineSerTicketRequirement`, while a vehicle that crosses into a new zone
with only a small movement must still be checked. Ahead of the zone
comparison, a small fixed GPS-noise floor
(`get_ser_ticket_creation_zone_change_floor_meters()`, default 10 meters,
technical/environment-only — not a user preference) skips the handler
entirely, without any zone lookup, when movement since the previous
recorded location is below it. When the floor is cleared (or there is no
previous location at all — a vehicle's first-ever recorded location always
proceeds), the SER zone containing the previous location and the SER zone
containing the event's coordinates are each resolved via
`FindContainingSerZone` and compared by `(city_code, zone_number)` (`None`
is its own distinct state). Only a genuine zone change proceeds to
`DetermineSerTicketRequirement`.

`DetermineSerTicketRequirement` itself is unchanged from
`ser-zone-ticket-notification`'s reuse of it, including exemption handling
and the active-ticket idempotency short-circuit — which is now itself
zone-aware (see the `ser-ticket-requirement` capability): an active ticket
for the *same* zone still suppresses creation, an active ticket for a
*different* zone no longer does.

When a ticket is required, calls CreateSerTicket.execute(...) —
CreateSerTicket itself is untouched, still exception-based, still used
unmodified by the manual POST /parking/ser-tickets endpoint (see design.md
decision 2).

Uses the event's own coordinates for CreateSerTicket's `location` argument
rather than a fresh GetLatestVehicleLocation lookup — avoids a redundant
query and guarantees the ticket is created for the exact location that was
just found inside a zone (see design.md decision 3).

On success, publishes SerTicketCreated. On any exception raised by
CreateSerTicket.execute, publishes SerTicketCreationFailed with a small
closed-vocabulary `reason` derived from the exception type — never
`str(exc)` — after logging the full exception via `logger.exception` for
observability (see design.md decision 2). Both events are published
exclusively by this handler; CreateSerTicket itself never publishes either.

The entire handler body is wrapped in a broad try/except + root trace span,
matching the sibling handler's convention (see
ser_ticket_notification_trigger_handler.py's module docstring) — a failure
here must never break the caller or block
SerTicketNotificationTriggerHandler from running for the same event.
"""

import logging
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.use_cases.create_ser_ticket import CreateSerTicket
from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.application.use_cases.find_containing_ser_zone import (
    FindContainingSerZone,
)
from mobility_manager.config import get_ser_ticket_creation_zone_change_floor_meters
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.events.ser_ticket_created import SerTicketCreated
from mobility_manager.domain.events.ser_ticket_creation_failed import (
    SerTicketCreationFailed,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderSessionNotFoundError,
    SerProviderVehicleNotFoundError,
    SerTicketPersistenceError,
    SerZoneNotFoundError,
)
from mobility_manager.domain.ports.event_publisher import EventPublisher
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)
from mobility_manager.domain.ports.user_ser_provider_config_repository import (
    UserSerProviderConfigRepository,
)
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.value_objects.location import GeoLocation, distance_m
from mobility_manager.infrastructure.observability.metrics import (
    record_ser_ticket_auto_creation,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)


def _zone_key(zone: SerZone | None) -> tuple[str | None, str | None]:
    """Return `(city_code, zone_number)` for `zone`, or `(None, None)` if `zone` is None."""
    if zone is None:
        return (None, None)
    return (zone.city_code, zone.zone_number)


def _map_exception_to_reason(exc: Exception) -> str:
    """
    Map an exception raised by CreateSerTicket.execute to a small
    closed-vocabulary reason string for SerTicketCreationFailed — never the
    raw exception message (see design.md decision 2).

    `SerTicketPersistenceError` maps to its own reason,
    `"ticket_created_but_not_recorded"`, distinguishing "the provider
    already created and charged a real ticket, but we failed to persist our
    own record of it" from an ordinary creation failure — see
    SerTicketNotificationTriggerHandler.on_ticket_creation_failed, which
    turns this specific reason (and only this one) into a
    `possibly_created=True` template kwarg (post-implementation fix 11.3).
    """
    if isinstance(exc, SerProviderSessionNotFoundError):
        return "no_provider_session"
    if isinstance(exc, SerZoneNotFoundError):
        return "zone_not_found"
    if isinstance(exc, SerProviderVehicleNotFoundError):
        return "vehicle_not_matched"
    if isinstance(exc, SerTicketPersistenceError):
        return "ticket_created_but_not_recorded"
    if isinstance(exc, SerProviderApiError):
        return "provider_error"
    return "provider_error"


class SerTicketCreationTriggerHandler:
    """Automatically creates a SER ticket when required, for owners who opted in via auto_create_ticket."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        vehicle_location_repo: VehicleLocationRepository,
        user_preferences_repo: UserPreferencesRepository,
        user_ser_provider_config_repo: UserSerProviderConfigRepository,
        find_containing_ser_zone: FindContainingSerZone,
        determine_ser_ticket_requirement: DetermineSerTicketRequirement,
        create_ser_ticket: CreateSerTicket,
        event_publisher: EventPublisher,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._vehicle_location_repo = vehicle_location_repo
        self._user_preferences_repo = user_preferences_repo
        self._user_ser_provider_config_repo = user_ser_provider_config_repo
        self._find_containing_ser_zone = find_containing_ser_zone
        self._determine_ser_ticket_requirement = determine_ser_ticket_requirement
        self._create_ser_ticket = create_ser_ticket
        self._event_publisher = event_publisher

    def handle(self, event: VehicleLocationUpdated) -> None:
        """
        Handle a VehicleLocationUpdated event.

        1. Look up the Vehicle. Skip silently if it no longer exists.
        2. Skip silently if the owner's `auto_create_ticket` is not `true`.
        3. If there is a previous recorded location, compute the distance to
           the event's coordinates. If it is below the fixed GPS-noise floor
           (`get_ser_ticket_creation_zone_change_floor_meters()`), skip
           silently without looking up any zone. Otherwise (or if there is
           no previous location at all — a vehicle's first-ever recorded
           location always proceeds), resolve the SER zone containing the
           previous location and the SER zone containing the event's
           coordinates, and skip silently if they are the same zone
           (`(city_code, zone_number)`, `None` as its own state).
        4. Check whether a ticket is required for the event's zone.
           Skip silently if not required (including a matching exemption).
        5. Resolve the provider (first of `list_connected_providers`) and
           call `CreateSerTicket.execute`, using the event's own
           coordinates as `location`.
        6. On success, publish `SerTicketCreated`.
        7. On any exception, publish `SerTicketCreationFailed` with a
           mapped `reason` — never the raw exception message.
        """
        with tracer.start_as_current_span("event_handler.ser_ticket_creation_trigger") as span:
            try:
                vehicle = self._vehicle_repo.get_by_id(event.vehicle_id)
                if vehicle is None:
                    logger.warning("Vehicle not found: %s", event.vehicle_id)
                    return

                preferences = self._user_preferences_repo.find_by_user_id(vehicle.user_id)
                if preferences is None or not preferences.auto_create_ticket:
                    logger.info("auto_create_ticket disabled for user: %s", vehicle.user_id)
                    return

                previous = self._vehicle_location_repo.get_previous(event.vehicle_id, before=event.received_at)
                # A vehicle's first-ever recorded location (no previous
                # location at all) does NOT skip this step and always
                # proceeds to the zone-requirement check below, since there
                # is no previous zone to compare against.
                if previous is not None:
                    distance = distance_m(previous.latitude, previous.longitude, event.latitude, event.longitude)
                    floor = get_ser_ticket_creation_zone_change_floor_meters()
                    if distance < floor:
                        logger.info(
                            "Movement below GPS-noise floor (%s meters) for vehicle: %s", distance, event.vehicle_id
                        )
                        return
                    previous_zone = self._find_containing_ser_zone.execute(
                        GeoLocation(lat=previous.latitude, lng=previous.longitude)
                    )
                    zone = self._find_containing_ser_zone.execute(
                        GeoLocation(lat=event.latitude, lng=event.longitude)
                    )
                    if _zone_key(previous_zone) == _zone_key(zone):
                        logger.info("SER zone unchanged for vehicle: %s", event.vehicle_id)
                        return
                else:
                    zone = self._find_containing_ser_zone.execute(
                        GeoLocation(lat=event.latitude, lng=event.longitude)
                    )

                if not self._determine_ser_ticket_requirement.execute(zone, event.vehicle_id, at=event.received_at):
                    logger.info("No SER ticket required for vehicle: %s", event.vehicle_id)
                    return

                if zone is None:
                    # Defensive — see SerTicketNotificationTriggerHandler's
                    # identical guard for rationale.
                    return

                self._create_ticket(vehicle.id, vehicle.user_id, zone.zone_number, event)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle VehicleLocationUpdated for vehicle: %s", event.vehicle_id)

    def _create_ticket(self, vehicle_id: UUID, user_id: UUID, zone_number: str, event: VehicleLocationUpdated) -> None:
        connected_providers = self._user_ser_provider_config_repo.list_connected_providers(user_id)
        if not connected_providers:
            logger.warning("No connected SER ticket provider for user: %s", user_id)
            record_ser_ticket_auto_creation(outcome="failed")
            self._event_publisher.publish(
                SerTicketCreationFailed(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                    zone_number=zone_number,
                    reason="no_provider_connected",
                )
            )
            return

        preferences = self._user_preferences_repo.find_by_user_id(user_id)
        duration_minutes = preferences.default_ticket_duration_minutes if preferences is not None else 60

        try:
            ticket = self._create_ser_ticket.execute(
                user_id=user_id,
                vehicle_id=vehicle_id,
                provider=connected_providers[0],
                duration_minutes=duration_minutes,
                location=GeoLocation(lat=event.latitude, lng=event.longitude),
            )
        except Exception as exc:
            logger.exception(
                "Automatic SER ticket creation failed: vehicle_id=%s user_id=%s zone_number=%s",
                vehicle_id,
                user_id,
                zone_number,
            )
            record_ser_ticket_auto_creation(outcome="failed")
            self._event_publisher.publish(
                SerTicketCreationFailed(
                    vehicle_id=vehicle_id,
                    user_id=user_id,
                    zone_number=zone_number,
                    reason=_map_exception_to_reason(exc),
                )
            )
            return

        record_ser_ticket_auto_creation(outcome="created")
        self._event_publisher.publish(
            SerTicketCreated(
                vehicle_id=vehicle_id,
                user_id=user_id,
                zone_number=zone_number,
                start_date=ticket.created_at,
                end_date=ticket.end_date,
            )
        )
        logger.info("Automatic SER ticket created for vehicle: %s", vehicle_id)
