"""
Application event handler: NotificationDispatchHandler.

Registered against VehicleLocationUpdated at application startup. This was
deliberate no-op scaffolding since add-telegram-notification-channel; this
change activates it — the first real notification kind, fired when a
vehicle moves more than a configurable distance since its previously
recorded location (see design.md decision 8).

Per-event-type opt-in/opt-out is explicitly out of scope here (deferred to a
later change): a user with any preferred_notification_channel connected
receives this notification kind unconditionally whenever the threshold is
met.
"""

from mobility_manager.application.notification_templates import render
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.config import get_notification_movement_threshold_meters
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
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


class NotificationDispatchHandler:
    """Notifies a vehicle's owner when it moves more than a configured distance."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        vehicle_location_repo: VehicleLocationRepository,
        user_preferences_repo: UserPreferencesRepository,
        send_notification: SendNotification,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._vehicle_location_repo = vehicle_location_repo
        self._user_preferences_repo = user_preferences_repo
        self._send_notification = send_notification

    def handle(self, event: VehicleLocationUpdated) -> None:
        """
        Handle a VehicleLocationUpdated event.

        Skips silently (no notification, no error) if: the vehicle no longer
        exists, this is the vehicle's first-ever recorded location (nothing
        to compare against), or the movement since the previous location is
        below the configured threshold.
        """
        vehicle = self._vehicle_repo.get_by_id(event.vehicle_id)
        if vehicle is None:
            return

        previous = self._vehicle_location_repo.get_previous(event.vehicle_id, before=event.recorded_at)
        if previous is None:
            return

        distance = distance_m(previous.latitude, previous.longitude, event.latitude, event.longitude)
        if distance < get_notification_movement_threshold_meters():
            return

        preferences = self._user_preferences_repo.find_by_user_id(vehicle.user_id)
        language = preferences.notification_language if preferences is not None else None
        text = render("vehicle_moved", language, plate=vehicle.license_plate or "")

        self._send_notification.execute(
            vehicle.user_id,
            NotificationMessage(
                text=text,
                location=GeoLocation(lat=event.latitude, lng=event.longitude),
            ),
        )
