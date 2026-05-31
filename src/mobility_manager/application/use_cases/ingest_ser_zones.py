"""
Use case: IngestSerZones.

Orchestrates download → parse → persist pipeline for Madrid SER zone data.
"""
import logging
from typing import Any

logger = logging.getLogger(__name__)


class IngestSerZones:
    """
    Use case that ingests SER zone data from the Madrid Callejero CSV.

    Dependencies are injected at construction time to keep this class
    infrastructure-agnostic.
    """

    def __init__(self, fetcher: Any, parser: Any, repo: Any) -> None:
        self._fetcher = fetcher
        self._parser = parser
        self._repo = repo

    def execute(self) -> dict[str, int]:
        """
        Run the full ingestion pipeline.

        Returns a summary dict: {total, skipped, inserted}.
        """
        logger.info("Starting SER zone ingestion")

        csv_text = self._fetcher.fetch()
        records, skipped = self._parser.parse(csv_text)

        raw_dicts = [
            {
                "street_name": r.street_name,
                "zone_code": r.zone_code,
                "zone_label": r.zone_label,
                "latitude": r.latitude,
                "longitude": r.longitude,
            }
            for r in records
        ]

        inserted = self._repo.bulk_replace(raw_dicts)

        summary = {
            "total": len(records) + skipped,
            "skipped": skipped,
            "inserted": inserted,
        }
        logger.info("SER zone ingestion complete: %s", summary)
        return summary
