"""
Use case: IngestSerZones.

Orchestrates the fetch → parse → persist pipeline for any city's SER-equivalent
parking data via a CityParkingDataProvider.
"""

import logging
from typing import Any

from mobility_manager.domain.ports.city_parking_data_provider import (
    CityParkingDataProvider,
)

logger = logging.getLogger(__name__)


class IngestSerZones:
    """
    Use case that ingests city parking data from a CityParkingDataProvider.

    The provider owns the full fetch-and-parse pipeline; this use case maps
    ParkingSpotRecord fields to the repository's expected dict structure
    and delegates persistence.
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

        raw_dicts = [
            {
                "street_name": r.street_name,
                "zone_type": r.zone_type,
                "spot_count": r.spot_count,
                "latitude": r.latitude,
                "longitude": r.longitude,
                "utm_x": r.utm_x,
                "utm_y": r.utm_y,
            }
            for r in records
        ]

        inserted = self._repo.bulk_replace(raw_dicts)

        summary = {"total": len(records), "inserted": inserted}
        logger.info("Ingestion complete [%s]: %s", city, summary)
        return summary
