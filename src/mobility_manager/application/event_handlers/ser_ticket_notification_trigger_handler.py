"""
Application event handler: SerTicketNotificationTriggerHandler.

Notification-only — it never creates a ticket, and never invokes a
SerTicketProvider. Automatic ticket creation is owned entirely by the sibling
SerTicketCreationTriggerHandler (see the ser-ticket-auto-creation capability),
which is subscribed to `VehicleLocationUpdated` and publishes
`SerTicketCreated` / `SerTicketCreationFailed` on completion.

The `ser_zone_ticket_required` notification is now triggered by
`SerTicketRequirementActivated`, published by
`SerTicketRequirementStateHandler` when the computed SER ticket requirement
for a vehicle transitions from inactive to active. This eliminates the
previous repeat-notification behavior: a stationary vehicle in an SER zone
produces exactly one activation event per requirement episode, and therefore
exactly one notification.

Registered against `SerTicketRequirementActivated`, `SerTicketCreated`, and
`SerTicketCreationFailed` at application startup. The handler evaluates each
recipient (owner + sharees) independently: the owner's `auto_create_ticket`
flag suppresses only the owner's notification path; sharees are still notified
if their preferences allow.

After a successful `ser_zone_ticket_required` send, the handler records an
audit row via `UserSerRequirementNotificationRepository` so the system can
answer "who was notified about which activation" later. Audit failures are
logged and swallowed; they do not affect notification delivery.

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
from datetime import UTC, datetime
from uuid import UUID, uuid4

from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode

from mobility_manager.application.datetime_formatting import format_local_datetime
from mobility_manager.application.notification_templates import render
from mobility_manager.application.use_cases.send_notification import SendNotification
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.events.ser_ticket_created import SerTicketCreated
from mobility_manager.domain.events.ser_ticket_creation_failed import (
    SerTicketCreationFailed,
)
from mobility_manager.domain.events.ser_ticket_requirement_activated import (
    SerTicketRequirementActivated,
)
from mobility_manager.domain.ports.notification_preferences_repository import (
    NotificationPreferencesRepository,
)
from mobility_manager.domain.ports.user_preferences_repository import (
    UserPreferencesRepository,
)
from mobility_manager.domain.ports.user_ser_requirement_notification_repository import (
    UserSerRequirementNotification,
    UserSerRequirementNotificationRepository,
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
    """Notifies a vehicle's accessors about SER-ticket-related events (never creates one itself)."""

    def __init__(
        self,
        vehicle_repo: VehicleRepository,
        user_preferences_repo: UserPreferencesRepository,
        notification_preferences_repo: NotificationPreferencesRepository,
        vehicle_share_repo: VehicleShareRepository,
        send_notification: SendNotification,
        notification_audit_repo: UserSerRequirementNotificationRepository,
    ) -> None:
        self._vehicle_repo = vehicle_repo
        self._user_preferences_repo = user_preferences_repo
        self._notification_preferences_repo = notification_preferences_repo
        self._vehicle_share_repo = vehicle_share_repo
        self._send_notification = send_notification
        self._notification_audit_repo = notification_audit_repo

    def _recipient_ids(self, vehicle_id: UUID) -> list[UUID]:
        """Return owner + sharee user ids for a vehicle."""
        vehicle = self._vehicle_repo.get_by_id(vehicle_id)
        if vehicle is None:
            return []
        shares = self._vehicle_share_repo.list_sharees(vehicle_id)
        return [vehicle.owner_id] + [share.user_id for share in shares]

    def on_requirement_activated(self, event: SerTicketRequirementActivated) -> None:
        """
        Handle a SerTicketRequirementActivated event.

        Looks up the vehicle first and skips silently if it no longer
        exists. Then evaluates each recipient (owner + sharees) independently:
        the owner's `auto_create_ticket` flag suppresses only the owner's
        notification path; sharees are still notified if their preferences
        allow. For each notified recipient, records an audit row.

        The whole method body is wrapped in a broad try/except so that a
        failure in any collaborator is contained here and never propagates
        to the caller — see module docstring. The whole call is also
        wrapped in a root trace span.
        """
        with tracer.start_as_current_span(
            "event_handler.ser_ticket_notification.on_requirement_activated"
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
                logger.exception("Failed to handle SerTicketRequirementActivated for vehicle: %s", event.vehicle_id)

    def _notify_ticket_required(
        self,
        recipient_id: UUID,
        vehicle: Vehicle,
        event: SerTicketRequirementActivated,
    ) -> None:
        """Notify a single recipient when a SER ticket requirement becomes active."""
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

        if event.zone_number is None:
            return

        preferences = self._user_preferences_repo.find_by_user_id(recipient_id)
        language = preferences.notification_language if preferences is not None else None
        text = render(
            _TYPE_KEY,
            language,
            plate=vehicle.license_plate or "",
            zone_number=event.zone_number,
        )

        self._send_notification.execute(
            recipient_id,
            NotificationMessage(
                text=text,
                location=GeoLocation(lat=event.latitude, lng=event.longitude),
            ),
        )
        logger.info("SER ticket required notification sent to user %s for vehicle: %s", recipient_id, event.vehicle_id)

        self._record_notification_audit(recipient_id, event)

    def _record_notification_audit(
        self,
        recipient_id: UUID,
        event: SerTicketRequirementActivated,
    ) -> None:
        """Record an audit row for a sent notification; failures are logged, not raised."""
        try:
            self._notification_audit_repo.save(
                UserSerRequirementNotification(
                    id=uuid4(),
                    user_id=recipient_id,
                    vehicle_id=event.vehicle_id,
                    city_code=event.city_code,
                    zone_number=event.zone_number,
                    latitude=event.latitude,
                    longitude=event.longitude,
                    requirement_activated_at=event.activated_at,
                    notified_at=datetime.now(UTC),
                )
            )
        except Exception:
            logger.exception(
                "Failed to record notification audit for user %s vehicle %s",
                recipient_id,
                event.vehicle_id,
            )

    def on_ticket_created(self, event: SerTicketCreated) -> None:
        """
        Handle a SerTicketCreated event, published by SerTicketCreationTriggerHandler.

        Fan out to the owner and all sharees, using each recipient's own
        `ser_ticket_created` preference and timezone. Wrapped in the same
        broad try/except + root trace span pattern as
        `on_requirement_activated`.
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
        try/except + root trace span pattern as `on_requirement_activated`.
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
