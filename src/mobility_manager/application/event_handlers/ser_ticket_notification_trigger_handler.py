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

Unlike NotificationDispatchHandler, a vehicle's first-ever recorded
location does NOT skip this handler — it always proceeds to the zone check
(once the preference gate passes), because there is no prior location to
compare against and a vehicle's very first fix could already be inside a
SER zone.

When the location is different enough, checks zone containment via
FindContainingSerZone and whether a ticket is currently required via
DetermineSerTicketRequirement, passing `event.vehicle_id` so a matching
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

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.datetime_formatting import format_local_datetime
from mobility_manager.application.notification_templates import render
from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.application.use_cases.find_containing_ser_zone import (
    FindContainingSerZone,
)
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.config import resolve_effective_threshold
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
from mobility_manager.domain.ports.vehicle_location_repository import (
    VehicleLocationRepository,
)
from mobility_manager.domain.ports.vehicle_repository import VehicleRepository
from mobility_manager.domain.value_objects.location import GeoLocation, distance_m
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
        vehicle_location_repo: VehicleLocationRepository,
        user_preferences_repo: UserPreferencesRepository,
        notification_preferences_repo: NotificationPreferencesRepository,
        find_containing_ser_zone: FindContainingSerZone,
        determine_ser_ticket_requirement: DetermineSerTicketRequirement,
        send_notification: SendNotification,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._vehicle_location_repo = vehicle_location_repo
        self._user_preferences_repo = user_preferences_repo
        self._notification_preferences_repo = notification_preferences_repo
        self._find_containing_ser_zone = find_containing_ser_zone
        self._determine_ser_ticket_requirement = determine_ser_ticket_requirement
        self._send_notification = send_notification

    def on_vehicle_location_updated(self, event: VehicleLocationUpdated) -> None:
        """
        Handle a VehicleLocationUpdated event.

        Looks up the vehicle first and skips silently if it no longer
        exists (matching NotificationDispatchHandler's ordering). Then
        skips silently, before any other lookup, if the owner's
        `auto_create_ticket` is `true` — SerTicketCreationTriggerHandler
        owns this event in that case, not this handler. Then checks the
        owner's `ser_zone_ticket_required` preference — skips silently (no
        notification, no error) if the row is missing or disabled, before
        any previous-location or zone lookup. When enabled, skips the SER
        zone lookup entirely when the location is unchanged relative to the
        vehicle's previous recorded location (below the owner's effective
        threshold for this type). A vehicle's first-ever recorded location
        does NOT count as "unchanged" — it always triggers a zone check.

        When the location is different enough, checks zone containment and
        whether a ticket is currently required. If required, looks up the
        vehicle owner's preferences, renders the localized "SER ticket
        required" message, and sends it.

        The whole method body is wrapped in a broad try/except so that a
        failure in any collaborator is contained here and never propagates
        to the caller — see module docstring. The whole call is also
        wrapped in a root trace span (this handler runs on its own
        thread-pool worker thread outside any HTTP request context — see
        design.md decision 4 and InMemoryEventPublisher's module docstring):
        the span records the exception and is marked as an error on
        failure, without changing the swallow-and-continue behavior itself.
        """
        with tracer.start_as_current_span(
            "event_handler.ser_ticket_notification.on_vehicle_location_updated"
        ) as span:
            try:
                vehicle = self._vehicle_repo.get_by_id(event.vehicle_id)
                if vehicle is None:
                    logger.warning("Vehicle not found: %s", event.vehicle_id)
                    return

                preferences = self._user_preferences_repo.find_by_user_id(vehicle.user_id)
                if preferences is not None and preferences.auto_create_ticket:
                    logger.info("auto_create_ticket enabled — skipping notification for vehicle: %s", vehicle.id)
                    return

                notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
                    vehicle.user_id, _TYPE_KEY
                )
                if notification_preference is None or not notification_preference.enabled:
                    logger.info("ser_zone_ticket_required notifications disabled for user: %s", vehicle.user_id)
                    return

                previous = self._vehicle_location_repo.get_previous(event.vehicle_id, before=event.received_at)
                # Unlike NotificationDispatchHandler (which skips entirely when
                # there is no previous location to compare against), a
                # first-ever location here still proceeds to the zone check
                # below — intentional divergence, see module docstring.
                if previous is not None:
                    distance = distance_m(previous.latitude, previous.longitude, event.latitude, event.longitude)
                    threshold = resolve_effective_threshold(notification_preference.config)
                    if distance < threshold:
                        logger.info("Movement below threshold (%s meters) for vehicle: %s", distance, event.vehicle_id)
                        return

                zone = self._find_containing_ser_zone.execute(GeoLocation(lat=event.latitude, lng=event.longitude))
                if not self._determine_ser_ticket_requirement.execute(zone, event.vehicle_id, at=event.received_at):
                    logger.info("No SER ticket required for vehicle: %s", event.vehicle_id)
                    return

                if zone is None:
                    # determine_ser_ticket_requirement only returned True for a
                    # real zone today, but this guard doesn't rely on that
                    # holding — see DetermineSerTicketRequirement's docstring
                    # for the factors it will grow next.
                    return

                language = preferences.notification_language if preferences is not None else None
                text = render(
                    _TYPE_KEY,
                    language,
                    plate=vehicle.license_plate or "",
                    zone_number=zone.zone_number,
                )

                self._send_notification.execute(
                    vehicle.user_id,
                    NotificationMessage(
                        text=text,
                        location=GeoLocation(lat=event.latitude, lng=event.longitude),
                    ),
                )
                logger.info("SER ticket required notification sent for vehicle: %s", event.vehicle_id)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle VehicleLocationUpdated for vehicle: %s", event.vehicle_id)

    def on_ticket_created(self, event: SerTicketCreated) -> None:
        """
        Handle a SerTicketCreated event, published by SerTicketCreationTriggerHandler.

        Skips silently if the owner's `ser_ticket_created` preference row is
        missing or disabled. Otherwise converts both `event.start_date` and
        `event.end_date` into the owner's configured timezone (falling back
        to UTC), renders the localized "ticket created" message, and sends
        it. Wrapped in the same broad try/except + root trace span pattern
        as `on_vehicle_location_updated` — see module docstring.
        """
        with tracer.start_as_current_span("event_handler.ser_ticket_notification.on_ticket_created") as span:
            try:
                notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
                    event.user_id, _CREATED_TYPE_KEY
                )
                if notification_preference is None or not notification_preference.enabled:
                    logger.info("ser_ticket_created notifications disabled for user: %s", event.user_id)
                    return

                preferences = self._user_preferences_repo.find_by_user_id(event.user_id)
                language = preferences.notification_language if preferences is not None else None
                timezone = preferences.timezone if preferences is not None else None

                text = render(
                    _CREATED_TYPE_KEY,
                    language,
                    zone_number=event.zone_number,
                    start_date=format_local_datetime(event.start_date, timezone),
                    end_date=format_local_datetime(event.end_date, timezone),
                )

                self._send_notification.execute(event.user_id, NotificationMessage(text=text, location=None))
                logger.info("SER ticket created notification sent for vehicle: %s", event.vehicle_id)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle SerTicketCreated for vehicle: %s", event.vehicle_id)

    def on_ticket_creation_failed(self, event: SerTicketCreationFailed) -> None:
        """
        Handle a SerTicketCreationFailed event, published by SerTicketCreationTriggerHandler.

        Skips silently if the owner's `ser_ticket_creation_failed`
        preference row is missing or disabled. Otherwise renders one
        localized failure message — using only `event.zone_number` and a
        derived `possibly_created: bool` boolean, never `event.reason`
        itself or any other technical detail — and sends it.
        `possibly_created` is `True` only when `event.reason ==
        "ticket_created_but_not_recorded"` (see
        SerTicketCreationTriggerHandler's exception-to-reason mapping): the
        template branches on this single boolean to warn the user a ticket
        may already exist, rather than ever interpolating `reason` itself
        into user-facing text (post-implementation fix 11.3). Wrapped in
        the same broad try/except + root trace span pattern as
        `on_vehicle_location_updated` — see module docstring.
        """
        with tracer.start_as_current_span("event_handler.ser_ticket_notification.on_ticket_creation_failed") as span:
            try:
                notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
                    event.user_id, _CREATION_FAILED_TYPE_KEY
                )
                if notification_preference is None or not notification_preference.enabled:
                    logger.info("ser_ticket_creation_failed notifications disabled for user: %s", event.user_id)
                    return

                preferences = self._user_preferences_repo.find_by_user_id(event.user_id)
                language = preferences.notification_language if preferences is not None else None

                possibly_created = event.reason == "ticket_created_but_not_recorded"
                text = render(
                    _CREATION_FAILED_TYPE_KEY,
                    language,
                    zone_number=event.zone_number,
                    possibly_created=possibly_created,
                )

                self._send_notification.execute(event.user_id, NotificationMessage(text=text, location=None))
                logger.info("SER ticket creation failed notification sent for vehicle: %s", event.vehicle_id)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle SerTicketCreationFailed for vehicle: %s", event.vehicle_id)
