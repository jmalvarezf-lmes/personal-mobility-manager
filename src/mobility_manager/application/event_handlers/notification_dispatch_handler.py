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
SerTicketNotificationTriggerHandler's own threshold for `ser_zone_ticket_required`.

The entire `handle` body is wrapped in a broad try/except: this handler is
subscribed on the same in-memory event publisher as
SerTicketNotificationTriggerHandler (see InMemoryEventPublisher.publish),
which dispatches each subscribed handler on its own thread-pool task (see
add-ser-ticket-auto-creation post-implementation fix 11.2) — an unhandled
exception here would not stop SerTicketNotificationTriggerHandler from
running for the same event, but would still be a silent failure of this
handler's own effect (e.g. a notification never sent) if left unguarded.
This handler must never break the caller — see
SerTicketNotificationTriggerHandler's module docstring for the identical
reasoning.
"""

import logging
from uuid import UUID

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.notification_templates import render
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.config import resolve_effective_threshold
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.ports.metrics_collector import MetricsCollector
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
from mobility_manager.domain.ports.vehicle_share_repository import (
    VehicleShareRepository,
)
from mobility_manager.domain.value_objects.location import GeoLocation, distance_m
from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
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
        vehicle_share_repo: VehicleShareRepository,
        send_notification: SendNotification,
        metrics_collector: MetricsCollector,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._vehicle_location_repo = vehicle_location_repo
        self._user_preferences_repo = user_preferences_repo
        self._notification_preferences_repo = notification_preferences_repo
        self._vehicle_share_repo = vehicle_share_repo
        self._send_notification = send_notification
        self._metrics_collector = metrics_collector

    def handle(self, event: VehicleLocationUpdated) -> None:
        """
        Handle a VehicleLocationUpdated event.

        Skips silently (no notification, no error) if: the vehicle no
        longer exists, this is the vehicle's first-ever recorded location
        (nothing to compare against), or no recipient has the movement
        exceed their effective threshold.

        Notifies the vehicle owner and every sharee independently, using
        each recipient's own notification preferences and movement threshold.

        The entire body is wrapped in a broad try/except so that a failure
        in any collaborator is contained here and never propagates to the
        caller — see module docstring. The whole call is also wrapped in a
        root trace span: the span records the exception and is marked as an
        error on failure, without changing the swallow-and-continue behavior.
        """
        with tracer.start_as_current_span("event_handler.notification_dispatch") as span:
            try:
                vehicle = self._vehicle_repo.get_by_id(event.vehicle_id)
                if vehicle is None:
                    logger.warning("Vehicle not found: %s", event.vehicle_id)
                    return

                shares = self._vehicle_share_repo.list_sharees(event.vehicle_id)
                recipient_ids = [vehicle.owner_id] + [share.user_id for share in shares]

                # Only look up the previous location if at least one recipient
                # has the notification enabled. This preserves the pre-sharing
                # contract: a disabled/missing owner preference skips before
                # VehicleLocationRepository.get_previous is called.
                enabled_recipients = [
                    recipient_id
                    for recipient_id in recipient_ids
                    if self._is_preference_enabled(recipient_id)
                ]
                if not enabled_recipients:
                    logger.info("location_moved notifications disabled for all recipients of vehicle: %s", event.vehicle_id)
                    return

                previous = self._vehicle_location_repo.get_previous(event.vehicle_id, before=event.received_at)
                if previous is None:
                    logger.info("No previous location for vehicle: %s", event.vehicle_id)
                    return

                distance = distance_m(previous.latitude, previous.longitude, event.latitude, event.longitude)

                for recipient_id in enabled_recipients:
                    self._notify_recipient(recipient_id, vehicle, event, distance)

            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR))
                logger.exception("Failed to handle VehicleLocationUpdated for vehicle: %s", event.vehicle_id)

    def _is_preference_enabled(self, recipient_id: UUID) -> bool:
        """Return True if the recipient has location_moved notifications enabled."""
        notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
            recipient_id, _TYPE_KEY
        )
        return notification_preference is not None and notification_preference.enabled

    def _notify_recipient(
        self,
        recipient_id: UUID,
        vehicle: Vehicle,
        event: VehicleLocationUpdated,
        distance: float,
    ) -> None:
        """Notify a single recipient if their preference and threshold allow it."""
        notification_preference = self._notification_preferences_repo.find_by_user_id_and_type(
            recipient_id, _TYPE_KEY
        )
        if notification_preference is None or not notification_preference.enabled:
            logger.info("location_moved notifications disabled for user: %s", recipient_id)
            return

        threshold = resolve_effective_threshold(notification_preference.config)
        if distance < threshold:
            logger.info(
                "Movement below threshold (%s meters) for user: %s, vehicle: %s",
                distance,
                recipient_id,
                vehicle.id,
            )
            return

        preferences = self._user_preferences_repo.find_by_user_id(recipient_id)
        language = preferences.notification_language if preferences is not None else None
        channel = preferences.preferred_notification_channel if preferences is not None else None
        text = render(_TYPE_KEY, language, plate=vehicle.license_plate or "")

        success = False
        try:
            success = self._send_notification.execute(
                recipient_id,
                NotificationMessage(
                    text=text,
                    location=GeoLocation(lat=event.latitude, lng=event.longitude),
                ),
            )
        finally:
            self._metrics_collector.record_notification_dispatch(channel=channel or "none", success=success)

        logger.info("Notification sent to user %s for vehicle: %s", recipient_id, vehicle.id)
