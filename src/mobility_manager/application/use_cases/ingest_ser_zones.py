"""
Use case: IngestSerZones.

Orchestrates the fetch → parse → persist pipeline for any city's SER-equivalent
parking data via a CityParkingDataProvider.
"""

import logging
from typing import Any

from shapely import wkt as shapely_wkt

from mobility_manager.domain.ports.city_parking_data_provider import (
    CityParkingDataProvider,
)

logger = logging.getLogger(__name__)


class IngestSerZones:
    """
    Use case that ingests city parking data from a CityParkingDataProvider.

    The provider owns the full fetch-and-parse pipeline; this use case maps
    SerZoneBoundaryRecord fields to the repository's expected dict structure
    (geometry serialized to WKT) and delegates persistence. The truncate-
    reload strategy now spans two tables (ser_zones, ser_zone_streets),
    handled atomically inside the repository's bulk_replace().
    """

    def __init__(self, provider: CityParkingDataProvider, repo: Any) -> None:
        self._provider = provider
        self._repo = repo

    def execute(self) -> dict[str, int]:
        """
        Run the full ingestion pipeline.

        Returns a summary dict: {total, inserted}.
        """
        city = self._provider.city_code
        logger.info("Starting parking data ingestion for city: %s", city)

        records = self._provider.get_records()

        if not records:
            logger.error(
                "Ingestion produced zero zone records [%s] — aborting to avoid wiping existing data",
                city,
            )
            raise RuntimeError(
                f"Ingestion for city {city!r} produced zero zone records; aborting without touching stored data"
            )

        raw_dicts = [
            {
                "zone_number": r.zone_number,
                "zone_type": r.zone_type,
                "district": r.district,
                "spot_count": r.spot_count,
                "geometry_wkt": shapely_wkt.dumps(r.geometry),
                "street_names": r.street_names,
            }
            for r in records
        ]

        inserted = self._repo.bulk_replace(raw_dicts)

        summary = {"total": len(records), "inserted": inserted}
        logger.info("Ingestion complete [%s]: %s", city, summary)
        return summary
