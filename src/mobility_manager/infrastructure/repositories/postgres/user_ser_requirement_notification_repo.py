"""
Infrastructure: PostgresUserSerRequirementNotificationRepository.

SQLAlchemy Core implementation of UserSerRequirementNotificationRepository.
Appends one audit row per notification sent about a SER requirement activation.
"""

from sqlalchemy.engine import Engine

from mobility_manager.domain.ports.user_ser_requirement_notification_repository import (
    UserSerRequirementNotification,
    UserSerRequirementNotificationRepository,
)
from mobility_manager.infrastructure.orm.tables import (
    user_ser_requirement_notifications_table,
)


class PostgresUserSerRequirementNotificationRepository(
    UserSerRequirementNotificationRepository
):
    """PostgreSQL-backed SER requirement notification audit repository using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def save(self, notification: UserSerRequirementNotification) -> None:
        """Persist a notification audit record."""
        with self._engine.begin() as conn:
            conn.execute(
                user_ser_requirement_notifications_table.insert().values(
                    id=notification.id,
                    user_id=notification.user_id,
                    vehicle_id=notification.vehicle_id,
                    city_code=notification.city_code,
                    zone_number=notification.zone_number,
                    latitude=notification.latitude,
                    longitude=notification.longitude,
                    requirement_activated_at=notification.requirement_activated_at,
                    notified_at=notification.notified_at,
                )
            )
