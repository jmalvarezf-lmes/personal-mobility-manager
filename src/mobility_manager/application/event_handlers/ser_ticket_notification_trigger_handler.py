"""
Application event handler: SerTicketNotificationTriggerHandler.

Renamed from SerTicketTriggerHandler (add-ser-ticket-auto-creation): this
handler is notification-only — it never creates a ticket, and never invokes a
SerTicketProvider. Automatic ticket creation is owned entirely by the sibling
SerTicketCreationTriggerHandler (see the ser-ticket-auto-creation capability),
which is subscribed to the same VehicleLocationUpdated event and publishes
SerTicketCreated / SerTicketCreationFailed on completion.

Registered against VehicleLocationUpdated at application startup. This was
deliberate no-op scaffolding since add-vehicle-location-notification, later
activated as an unconditional-per-user-channel notification that reused
NotificationDispatchHandler's previous-location/threshold distance check
(see design.md). add-notification-type-preferences gated it behind the
owner's `ser_zone_ticket_required` notification preference, checked
immediately after the vehicle lookup — a user only receives this
notification kind after explicitly enabling it via
PUT /notifications/preferences/ser_zone_ticket_required — and resolves its
own effective movement threshold independently of
NotificationDispatchHandler's threshold for `location_moved`: the two never
share a single call or value.

add-ser-ticket-auto-creation adds one more early exit, immediately after the
vehicle lookup and before the `ser_zone_ticket_required` preference check:
when the owner's `UserPreferences.auto_create_ticket` is `true`,
SerTicketCreationTriggerHandler owns this event instead, and this handler
skips entirely — no "ticket required" obligation notice is sent, since the
system is about to (attempt to) handle it automatically. This handler's
`on_vehicle_location_updated` renamed from `handle` in the same change, so
all three event-subscribed methods on this class share one `on_<event>`
naming convention (see design.md decision 1).

The "is this ping worth acting on" decision (previously: this handler's own
previous-location/distance check) is now delegated to the shared
`SerZoneRecheckGate` collaborator (see change-ser-ticket-stationary-recheck
design.md D3/D4/D5): this handler passes its own effective movement
threshold (the owner's `ser_zone_ticket_required` preference `threshold_m`
if set, otherwise `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` —
independent of `SerTicketCreationTriggerHandler`'s own floor, never sharing
a call or value) as `movement_floor_meters`. The gate applies that floor
plus a zone-unchanged skip only while the vehicle holds an active
`ParkingTicket` (a gain for this handler — it previously lacked the
zone-unchanged optimization entirely); when it holds none, the gate always
signals a recheck regardless of movement or zone, since time alone
(enforcement schedule activation, an existing ticket's expiry) can flip the
requirement for a stationary vehicle.

When the gate signals `should_check=True`, its resolved `zone` is checked
via DetermineSerTicketRequirement, passing `event.vehicle_id` so a matching
per-vehicle SER parking exemption (see the vehicle-ser-parking-exemption
capability) suppresses the requirement the same as an inactive enforcement
schedule would. If a ticket is still required, it notifies the vehicle
owner via their preferred channel that a SER ticket must be created.

This handler also subscribes to SerTicketCreated and SerTicketCreationFailed
(published by SerTicketCreationTriggerHandler) via `on_ticket_created` and
`on_ticket_creation_failed`, and is the sole place in the system that calls
SendNotification for anything SER-ticket related — keeping "decide
whether/what to create" and "tell the user about SER-ticket-related things"
as two separate responsibilities (see design.md decision 1).

Every subscribed method's body is wrapped in a broad try/except: this
handler is subscribed on the same in-memory event publisher as its siblings
(see InMemoryEventPublisher.publish), which dispatches each subscribed
handler on its own thread-pool task (see add-ser-ticket-auto-creation
post-implementation fix 11.2) — an unhandled exception here would not stop
other handlers from running for the same event, but would still be a silent
failure of this handler's own effect (e.g. a notification never sent) if
left unguarded. This handler must never break the caller.
"""

import logging
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.datetime_formatting import format_local_datetime
from mobility_manager.application.notification_templates import render
from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckGate,
)
from mobility_manager.config import resolve_effective_threshold
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.events.ser_ticket_created import SerTicketCreated
from mobility_manager.domain.events.ser_ticket_creation_failed import (
    SerTicketCreationFailed,
)
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.notification_preferences_repository import (
    NotificationPreferencesRepository,
)
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.ports.vehicle_share_repository import (
    VehicleShareRepository,
)
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

_TYPE_KEY = "ser_zone_ticket_required"
_CREATED_TYPE_KEY = "ser_ticket_created"
_CREATION_FAILED_TYPE_KEY = "ser_ticket_creation_failed"


class SerTicketNotificationTriggerHandler:
    """Notifies a vehicle's owner about SER-ticket-related events (never creates one itself)."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        user_preferences_repo: UserPreferencesRepository,
        notification_preferences_repo: NotificationPreferencesRepository,
        vehicle_share_repo: VehicleShareRepository,
        determine_ser_ticket_requirement: DetermineSerTicketRequirement,
        ser_zone_recheck_gate: SerZoneRecheckGate,
        send_notification: SendNotification,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._user_preferences_repo = user_preferences_repo
        self._notification_preferences_repo = notification_preferences_repo
        self._vehicle_share_repo = vehicle_share_repo
        self._determine_ser_ticket_requirement = determine_ser_ticket_requirement
        self._ser_zone_recheck_gate = ser_zone_recheck_gate
        self._send_notification = send_notification

    def _recipient_ids(self, vehicle_id: UUID) -> list[UUID]:
        """Return owner + sharee user ids for a vehicle."""
        vehicle = self._vehicle_repo.get_by_id(vehicle_id)
        if vehicle is None:
            return []
        shares = self._vehicle_share_repo.list_sharees(vehicle_id)
        return [vehicle.owner_id] + [share.user_id for share in shares]

    def on_vehicle_location_updated(self, event: VehicleLocationUpdated) -> None:
        """
        Handle a VehicleLocationUpdated event.

        Looks up the vehicle first and skips silently if it no longer
        exists. Then evaluates each recipient (owner + sharees) independently:
        the owner's `auto_create_ticket` flag suppresses only the owner's
        notification path; sharees are still notified if their preferences
        allow. For each recipient, checks their own `ser_zone_ticket_required`
        preference and effective threshold, calls `SerZoneRecheckGate.evaluate`,
        determines whether a ticket is required, and sends the notification.

        The whole method body is wrapped in a broad try/except so that a
        failure in any collaborator is contained here and never propagates
        to the caller — see module docstring. The whole call is also
        wrapped in a root trace span.
        """
        with tracer.start_as_current_span(
            "event_handler.ser_ticket_notification.on_vehicle_location_updated"
        ) as span:
            try:
                vehicle = self._vehicle_repo.get_by_id(event.vehicle_id)
                if vehicle is None:
                    logger.warning("Vehicle not found: %s", event.vehicle_id)
                    return

                shares = self._vehicle_share_repo.list_sharees(event.vehicle_id)
                recipient_ids = [vehicle.owner_id] + [share.user_id for share in shares]

                for recipient_id in recipient_ids:
                    try:
                        self._notify_ticket_required(recipient_id, vehicle, event)
                    except Exception as exc:
                        # Per-recipient failures must not abort the fan-out to
                        # the owner and remaining sharees. Record the failure on
                        # the span and continue.
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR))
                        logger.exception(
                            "Failed to notify recipient %s for vehicle: %s",
                            recipient_id,
                            event.vehicle_id,
                        )

            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle VehicleLocationUpdated for vehicle: %s", event.vehicle_id)

    def _notify_ticket_required(
        self,
        recipient_id: UUID,
        vehicle: Vehicle,
        event: VehicleLocationUpdated,
    ) -> None:
        """Notify a single recipient when a SER ticket is required."""
        owner_preferences = self._user_preferences_repo.find_by_user_id(vehicle.owner_id)
        if recipient_id == vehicle.owner_id and owner_preferences is not None and owner_preferences.auto_create_ticket:
            logger.info("auto_create_ticket enabled — skipping owner notification for vehicle: %s", vehicle.id)
            return

        notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
            recipient_id, _TYPE_KEY
        )
        if notification_preference is None or not notification_preference.enabled:
            logger.info("ser_zone_ticket_required notifications disabled for user: %s", recipient_id)
            return

        threshold = resolve_effective_threshold(notification_preference.config)
        decision = self._ser_zone_recheck_gate.evaluate(event, movement_floor_meters=threshold)
        if not decision.should_check:
            return
        zone = decision.zone

        if not self._determine_ser_ticket_requirement.execute(zone, event.vehicle_id, at=event.received_at):
            logger.info("No SER ticket required for vehicle: %s", event.vehicle_id)
            return

        if zone is None:
            return

        preferences = self._user_preferences_repo.find_by_user_id(recipient_id)
        language = preferences.notification_language if preferences is not None else None
        text = render(
            _TYPE_KEY,
            language,
            plate=vehicle.license_plate or "",
            zone_number=zone.zone_number,
        )

        self._send_notification.execute(
            recipient_id,
            NotificationMessage(
                text=text,
                location=GeoLocation(lat=event.latitude, lng=event.longitude),
            ),
        )
        logger.info("SER ticket required notification sent to user %s for vehicle: %s", recipient_id, event.vehicle_id)

    def on_ticket_created(self, event: SerTicketCreated) -> None:
        """
        Handle a SerTicketCreated event, published by SerTicketCreationTriggerHandler.

        Fan out to the owner and all sharees, using each recipient's own
        `ser_ticket_created` preference and timezone. Wrapped in the same
        broad try/except + root trace span pattern as
        `on_vehicle_location_updated`.
        """
        with tracer.start_as_current_span("event_handler.ser_ticket_notification.on_ticket_created") as span:
            try:
                recipient_ids = self._recipient_ids(event.vehicle_id)
                for recipient_id in recipient_ids:
                    try:
                        self._notify_ticket_created(recipient_id, event)
                    except Exception as exc:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR))
                        logger.exception(
                            "Failed to notify recipient %s for vehicle: %s",
                            recipient_id,
                            event.vehicle_id,
                        )
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle SerTicketCreated for vehicle: %s", event.vehicle_id)

    def _notify_ticket_created(self, recipient_id: UUID, event: SerTicketCreated) -> None:
        """Notify a single recipient that an automatic SER ticket was created."""
        notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
            recipient_id, _CREATED_TYPE_KEY
        )
        if notification_preference is None or not notification_preference.enabled:
            logger.info("ser_ticket_created notifications disabled for user: %s", recipient_id)
            return

        preferences = self._user_preferences_repo.find_by_user_id(recipient_id)
        language = preferences.notification_language if preferences is not None else None
        timezone = preferences.timezone if preferences is not None else None

        text = render(
            _CREATED_TYPE_KEY,
            language,
            zone_number=event.zone_number,
            start_date=format_local_datetime(event.start_date, timezone),
            end_date=format_local_datetime(event.end_date, timezone),
        )

        self._send_notification.execute(recipient_id, NotificationMessage(text=text, location=None))
        logger.info("SER ticket created notification sent to user %s for vehicle: %s", recipient_id, event.vehicle_id)

    def on_ticket_creation_failed(self, event: SerTicketCreationFailed) -> None:
        """
        Handle a SerTicketCreationFailed event, published by SerTicketCreationTriggerHandler.

        Fan out to the owner and all sharees, using each recipient's own
        `ser_ticket_creation_failed` preference. Wrapped in the same broad
        try/except + root trace span pattern as `on_vehicle_location_updated`.
        """
        with tracer.start_as_current_span(
            "event_handler.ser_ticket_notification.on_ticket_creation_failed"
        ) as span:
            try:
                recipient_ids = self._recipient_ids(event.vehicle_id)
                for recipient_id in recipient_ids:
                    try:
                        self._notify_ticket_creation_failed(recipient_id, event)
                    except Exception as exc:
                        span.record_exception(exc)
                        span.set_status(Status(StatusCode.ERROR))
                        logger.exception(
                            "Failed to notify recipient %s for vehicle: %s",
                            recipient_id,
                            event.vehicle_id,
                        )
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle SerTicketCreationFailed for vehicle: %s", event.vehicle_id)

    def _notify_ticket_creation_failed(self, recipient_id: UUID, event: SerTicketCreationFailed) -> None:
        """Notify a single recipient that automatic SER ticket creation failed."""
        notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
            recipient_id, _CREATION_FAILED_TYPE_KEY
        )
        if notification_preference is None or not notification_preference.enabled:
            logger.info("ser_ticket_creation_failed notifications disabled for user: %s", recipient_id)
            return

        preferences = self._user_preferences_repo.find_by_user_id(recipient_id)
        language = preferences.notification_language if preferences is not None else None

        possibly_created = event.reason == "ticket_created_but_not_recorded"
        text = render(
            _CREATION_FAILED_TYPE_KEY,
            language,
            zone_number=event.zone_number,
            possibly_created=possibly_created,
        )

        self._send_notification.execute(recipient_id, NotificationMessage(text=text, location=None))
        logger.info(
            "SER ticket creation failed notification sent to user %s for vehicle: %s",
            recipient_id,
            event.vehicle_id,
        )
