"""
Infrastructure: PostgresElParkingZoneMappingRepository.

Infra-internal cache repository — NOT a domain port, since its column
vocabulary (id_ser_town, id_ser_zone/rate ids nested inside zones_payload) is
ElParking-specific and must never leak past SerTicketProviderPort. Backs the
`ser_ticket_provider_zone_mappings` table, keyed by (city_code, provider),
refreshed lazily by ElParkingSerTicketProvider on a cache miss or a
`fetched_at` older than 30 days (see design.md decision 4).
"""

import logging
from dataclasses import asdict
from datetime import UTC, datetime, timedelta

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from mobility_manager.infrastructure.orm.tables import (
    ser_ticket_provider_zone_mappings_table,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
    ElParkingRate,
    ElParkingZone,
    ElParkingZoneMapping,
)

logger = logging.getLogger(__name__)

_FRESHNESS_WINDOW = timedelta(days=30)


class PostgresElParkingZoneMappingRepository:
    """PostgreSQL-backed cache of ElParking's town/zone/rate ID mapping, per (city_code, provider)."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def get(self, city_code: str, provider: str) -> ElParkingZoneMapping | None:
        """
        Return the cached mapping for (city_code, provider), or None if
        missing, or if its `fetched_at` is 30 or more days old.
        """
        with self._engine.connect() as conn:
            row = conn.execute(
                ser_ticket_provider_zone_mappings_table.select().where(
                    ser_ticket_provider_zone_mappings_table.c.city_code == city_code,
                    ser_ticket_provider_zone_mappings_table.c.provider == provider,
                )
            ).fetchone()

        if row is None:
            return None

        fetched_at: datetime = row.fetched_at
        if fetched_at.tzinfo is None:
            fetched_at = fetched_at.replace(tzinfo=UTC)

        if datetime.now(UTC) - fetched_at >= _FRESHNESS_WINDOW:
            return None

        try:
            zones = [
                ElParkingZone(
                    id=z["id"],
                    name=z["name"],
                    polygon_wkt=z["polygon_wkt"],
                    rates=[ElParkingRate(id=r["id"], name=r["name"]) for r in z.get("rates", [])],
                )
                for z in row.zones_payload
            ]
        except (KeyError, TypeError) as exc:
            # A structurally malformed cache row is treated as a cache miss
            # rather than crashing — the caller re-fetches from ElParking
            # on a None return, same as a missing or stale row.
            logger.warning(
                "Malformed zones_payload for (city_code=%s, provider=%s): %s", city_code, provider, exc
            )
            return None

        return ElParkingZoneMapping(id_ser_town=row.id_ser_town, zones=zones, fetched_at=fetched_at)

    def save(self, city_code: str, provider: str, mapping: ElParkingZoneMapping) -> None:
        """Upsert the given mapping for (city_code, provider), stamping `fetched_at` as now."""
        zones_payload = [
            {"id": z.id, "name": z.name, "polygon_wkt": z.polygon_wkt, "rates": [asdict(r) for r in z.rates]}
            for z in mapping.zones
        ]

        stmt = insert(ser_ticket_provider_zone_mappings_table).values(
            city_code=city_code,
            provider=provider,
            id_ser_town=mapping.id_ser_town,
            zones_payload=zones_payload,
            fetched_at=datetime.now(UTC),
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["city_code", "provider"],
            set_={
                "id_ser_town": stmt.excluded.id_ser_town,
                "zones_payload": stmt.excluded.zones_payload,
                "fetched_at": stmt.excluded.fetched_at,
            },
        )

        with self._engine.begin() as conn:
            conn.execute(stmt)
