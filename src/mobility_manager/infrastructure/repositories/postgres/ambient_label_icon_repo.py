"""
Infrastructure: PostgresAmbientLabelIconRepository.

Caches the DGT sticker icon image bytes keyed by label value (B/C/ECO/0
only — see design.md decision 8). Uses INSERT ... ON CONFLICT DO UPDATE for
save, mirroring PostgresVehicleAmbientLabelRepository.upsert().
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.domain.ports.ambient_label_icon_repository import (
    AmbientLabelIcon,
    AmbientLabelIconRepository,
)
from mobility_manager.domain.value_objects.ambient_label import AmbientLabel
from mobility_manager.infrastructure.orm.tables import ambient_label_icons_table


class PostgresAmbientLabelIconRepository(AmbientLabelIconRepository):
    """PostgreSQL-backed ambient label icon cache using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get_by_label(self, label: AmbientLabel) -> AmbientLabelIcon | None:
        """Return the cached icon for the label, or None on a cache miss."""
        with self._engine.connect() as conn:
            row = conn.execute(
                select(ambient_label_icons_table).where(ambient_label_icons_table.c.label == label.value)
            ).fetchone()
        if row is None:
            return None
        return AmbientLabelIcon(image_bytes=row.image_bytes, content_type=row.content_type)

    def save(self, label: AmbientLabel, image_bytes: bytes, content_type: str) -> None:
        """Cache the icon bytes (and content type) for the given label."""
        now = datetime.now(UTC)
        stmt = (
            insert(ambient_label_icons_table)
            .values(
                label=label.value,
                image_bytes=image_bytes,
                content_type=content_type,
                fetched_at=now,
            )
            .on_conflict_do_update(
                index_elements=["label"],
                set_={"image_bytes": image_bytes, "content_type": content_type, "fetched_at": now},
            )
        )
        with self._engine.begin() as conn:
            conn.execute(stmt)
