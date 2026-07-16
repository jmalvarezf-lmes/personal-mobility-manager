"""
Application event handler: SerTicketTriggerHandler.

Registered against VehicleLocationUpdated at application startup. This was
deliberate no-op scaffolding since add-vehicle-location-notification, later
activated as an unconditional-per-user-channel notification that reused
NotificationDispatchHandler's previous-location/threshold distance check
(see design.md). This change (add-notification-type-preferences) gates it
behind the owner's `ser_zone_ticket_required` notification preference,
checked immediately after the vehicle lookup — a user only receives this
notification kind after explicitly enabling it via
PUT /notifications/preferences/ser_zone_ticket_required — and resolves its
own effective movement threshold independently of
NotificationDispatchHandler's threshold for `location_moved`: the two never
share a single call or value.

Unlike NotificationDispatchHandler, a vehicle's first-ever recorded
location does NOT skip this handler — it always proceeds to the zone check
(once the preference gate passes), because there is no prior location to
compare against and a vehicle's very first fix could already be inside a
SER zone.

When the location is different enough, checks zone containment via
FindContainingSerZone and whether a ticket is currently required via
DetermineSerTicketRequirement. If so, it notifies the vehicle owner via
their preferred channel that a SER ticket must be created.

This change is notification-only: no ticket is created, and no
SerTicketProvider is invoked. Automatic ticket creation remains out of
scope.

The entire `handle` body is wrapped in a broad try/except: this handler is
subscribed on the same synchronous, unguarded in-memory event publisher as
NotificationDispatchHandler (see InMemoryEventPublisher.publish), which
invokes subscribed handlers in a loop with no per-handler exception
isolation. An unhandled exception here would both stop
NotificationDispatchHandler from running for that event and propagate out
as an unhandled error on the push-ingestion HTTP path, even though the
vehicle location was already durably saved before publish was called. This
handler must never break the caller.
"""

import logging

from mobility_manager.application.notification_templates import render
from mobility_manager.application.use_cases.determine_ser_ticket_requirement import (
    DetermineSerTicketRequirement,
)
from mobility_manager.application.use_cases.find_containing_ser_zone import (
    FindContainingSerZone,
)
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.config import resolve_effective_threshold
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

_TYPE_KEY = "ser_zone_ticket_required"


class SerTicketTriggerHandler:
    """Notifies a vehicle's owner when a SER ticket is required for its location."""

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

    def handle(self, event: VehicleLocationUpdated) -> None:
        """
        Handle a VehicleLocationUpdated event.

        Looks up the vehicle first and skips silently if it no longer
        exists (matching NotificationDispatchHandler's ordering). Then
        checks the owner's `ser_zone_ticket_required` preference — skips
        silently (no notification, no error) if the row is missing or
        disabled, before any previous-location or zone lookup. When
        enabled, skips the SER zone lookup entirely when the location is
        unchanged relative to the vehicle's previous recorded location
        (below the owner's effective threshold for this type). A vehicle's
        first-ever recorded location does NOT count as "unchanged" — it
        always triggers a zone check.

        When the location is different enough, checks zone containment and
        whether a ticket is currently required. If required, looks up the
        vehicle owner's preferences, renders the localized "SER ticket
        required" message, and sends it.

        The whole method body is wrapped in a broad try/except so that a
        failure in any collaborator (vehicle lookup, preference lookup,
        previous-location lookup, zone lookup, requirement check,
        preferences lookup, notification send) is contained here and never
        propagates to the caller — see module docstring.
        """
        try:
            vehicle = self._vehicle_repo.get_by_id(event.vehicle_id)
            if vehicle is None:
                logger.warning("Vehicle not found: %s", event.vehicle_id)
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
            if not self._determine_ser_ticket_requirement.execute(zone):
                logger.info("No SER ticket required for vehicle: %s", event.vehicle_id)
                return

            if zone is None:
                # determine_ser_ticket_requirement only returned True for a
                # real zone today, but this guard doesn't rely on that
                # holding — see DetermineSerTicketRequirement's docstring
                # for the factors it will grow next.
                return

            preferences = self._user_preferences_repo.find_by_user_id(vehicle.user_id)
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
        except Exception:
            logger.exception("Failed to handle VehicleLocationUpdated for vehicle: %s", event.vehicle_id)
