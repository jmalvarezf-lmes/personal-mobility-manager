"""
Application event handler: NotificationDispatchHandler.

Registered against VehicleLocationUpdated at application startup. This was
deliberate no-op scaffolding since add-telegram-notification-channel; a
later change activated it as an unconditional-per-user-channel notification;
this change (add-notification-type-preferences) gates it behind the owner's
`location_moved` notification preference — a user only receives this
notification kind after explicitly enabling it via
PUT /notifications/preferences/location_moved. The effective movement
threshold is resolved per-user (config.threshold_m, falling back to
DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS), independently of
SerTicketTriggerHandler's own threshold for `ser_zone_ticket_required`.

The entire `handle` body is wrapped in a broad try/except: this handler is
subscribed on the same synchronous, unguarded in-memory event publisher as
SerTicketTriggerHandler (see InMemoryEventPublisher.publish), which invokes
subscribed handlers in a loop with no per-handler exception isolation. An
unhandled exception here would both stop SerTicketTriggerHandler from
running for that event and propagate out as an unhandled error on the
push-ingestion HTTP path, even though the vehicle location was already
durably saved before publish was called. This handler must never break the
caller — see SerTicketTriggerHandler's module docstring for the identical
reasoning.
"""

import logging

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.notification_templates import render
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
from mobility_manager.infrastructure.observability.metrics import (
    record_notification_dispatch,
)

logger = logging.getLogger(__name__)
tracer = trace.get_tracer(__name__)

_TYPE_KEY = "location_moved"


class NotificationDispatchHandler:
    """Notifies a vehicle's owner when it moves more than a configured distance."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        vehicle_location_repo: VehicleLocationRepository,
        user_preferences_repo: UserPreferencesRepository,
        notification_preferences_repo: NotificationPreferencesRepository,
        send_notification: SendNotification,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._vehicle_location_repo = vehicle_location_repo
        self._user_preferences_repo = user_preferences_repo
        self._notification_preferences_repo = notification_preferences_repo
        self._send_notification = send_notification

    def handle(self, event: VehicleLocationUpdated) -> None:
        """
        Handle a VehicleLocationUpdated event.

        Skips silently (no notification, no error) if: the vehicle no
        longer exists, the owner's `location_moved` preference is missing
        or disabled (checked immediately after the vehicle lookup, before
        any previous-location lookup), this is the vehicle's first-ever
        recorded location (nothing to compare against), or the movement
        since the previous location is below the owner's effective
        threshold for this type.

        The entire body is wrapped in a broad try/except so that a failure
        in any collaborator is contained here and never propagates to the
        caller — see module docstring. The whole call is also wrapped in a
        root trace span (this handler runs synchronously outside any HTTP
        request context — see design.md decision 4): the span records the
        exception and is marked as an error on failure, without changing
        the swallow-and-continue behavior itself. A
        record_notification_dispatch() metric is recorded once per
        send_notification attempt, labeled by channel and outcome.
        """
        with tracer.start_as_current_span("event_handler.notification_dispatch") as span:
            try:
                vehicle = self._vehicle_repo.get_by_id(event.vehicle_id)
                if vehicle is None:
                    logger.warning("Vehicle not found: %s", event.vehicle_id)
                    return

                notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
                    vehicle.user_id, _TYPE_KEY
                )
                if notification_preference is None or not notification_preference.enabled:
                    logger.info("location_moved notifications disabled for user: %s", vehicle.user_id)
                    return

                previous = self._vehicle_location_repo.get_previous(event.vehicle_id, before=event.received_at)
                if previous is None:
                    logger.info("No previous location for vehicle: %s", event.vehicle_id)
                    return

                distance = distance_m(previous.latitude, previous.longitude, event.latitude, event.longitude)
                threshold = resolve_effective_threshold(notification_preference.config)
                if distance < threshold:
                    logger.info("Movement below threshold (%s meters) for vehicle: %s", distance, event.vehicle_id)
                    return

                preferences = self._user_preferences_repo.find_by_user_id(vehicle.user_id)
                language = preferences.notification_language if preferences is not None else None
                channel = preferences.preferred_notification_channel if preferences is not None else None
                text = render(_TYPE_KEY, language, plate=vehicle.license_plate or "")

                success = False
                try:
                    success = self._send_notification.execute(
                        vehicle.user_id,
                        NotificationMessage(
                            text=text,
                            location=GeoLocation(lat=event.latitude, lng=event.longitude),
                        ),
                    )
                finally:
                    # channel/success only — no user id, plate, or free-text
                    # value (see design.md decision 7).
                    record_notification_dispatch(channel=channel or "none", success=success)

                logger.info("Notification sent for vehicle: %s", event.vehicle_id)
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle VehicleLocationUpdated for vehicle: %s", event.vehicle_id)
