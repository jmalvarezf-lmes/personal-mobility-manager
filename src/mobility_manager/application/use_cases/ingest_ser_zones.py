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
    SerZoneBoundaryRecord/ZoneArea fields to the repository's expected dict
    structures (geometry serialized to WKT) and delegates persistence. The
    truncate-reload strategy spans three tables (ser_zones, ser_zone_streets,
    ser_zone_areas), handled atomically inside the repository's
    bulk_replace() — see add-ser-zone-frontiers design.md D5/risks.
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

        records, zone_areas = self._provider.get_records_and_zone_areas()

        if not records:
            logger.error(
                "Ingestion produced zero zone records [%s] — aborting to avoid wiping existing data",
                city,
            )
            raise RuntimeError(
                f"Ingestion for city {city!r} produced zero zone records; aborting without touching stored data"
            )

        if not zone_areas:
            # records is non-empty at this point (checked above), so a
            # zero-length zone_areas result here means the zone-area half of
            # the pipeline degraded independently (e.g. the Barrios
            # shapefile fetch yielded zero usable records) — abort before
            # touching any of the three tables, the same partial-write bug
            # class fixed for the discarded Voronoi-based attempt's review
            # pass.
            logger.error(
                "Ingestion produced non-empty records but zero zone areas [%s] — "
                "aborting to avoid a partial write that would silently leave ser_zone_areas empty",
                city,
            )
            raise RuntimeError(
                f"Ingestion for city {city!r} produced records but zero zone areas; "
                "aborting without touching stored data"
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

        zone_area_dicts = [
            {
                "zone_number": za.zone_number,
                "neighbourhood": za.neighbourhood,
                "geometry_wkt": shapely_wkt.dumps(za.geometry),
            }
            for za in zone_areas
        ]

        inserted = self._repo.bulk_replace(raw_dicts, zone_areas=zone_area_dicts)

        summary = {"total": len(records), "inserted": inserted}
        logger.info("Ingestion complete [%s]: %s", city, summary)
        return summary
