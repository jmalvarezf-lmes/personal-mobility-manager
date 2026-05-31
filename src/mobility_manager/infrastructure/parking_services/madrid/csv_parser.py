"""
Infrastructure: CallejeroCsvParser.

Parses the Madrid Callejero CSV, reprojects coordinates from ETRS89 UTM Zone 30N
(EPSG:25830) to WGS84 (EPSG:4326), and maps zone codes to human-readable labels.
"""
import csv
import io
import logging
import math
from dataclasses import dataclass

from pyproj import Transformer

logger = logging.getLogger(__name__)

# Mapping from raw SER zone codes found in the Madrid dataset to human-readable labels.
# Codes follow the pattern used in the callejero CSV export.
ZONE_LABELS: dict[str, str] = {
    "SER-A": "Blue",         # Zona Azul
    "SER-V": "Green",        # Zona Verde
    "SER-N": "Residential",  # Zona Naranja (residents)
    "SER-G": "Grey",
    "A": "Blue",
    "V": "Green",
    "N": "Residential",
    "G": "Grey",
    # Add more as discovered from data
}

# Madrid bounding box (WGS84) — records outside this box are discarded.
_MADRID_LAT_MIN = 39.8
_MADRID_LAT_MAX = 41.2
_MADRID_LNG_MIN = -4.6
_MADRID_LNG_MAX = -2.9


@dataclass
class SerZoneRecord:
    street_name: str
    zone_code: str
    zone_label: str
    latitude: float
    longitude: float


class CallejeroCsvParser:
    """Parses the Madrid Callejero CSV and reprojects coordinates to WGS84."""

    # Column names expected in the Madrid callejero CSV (case-insensitive lookup).
    # These are configurable class attributes so they can be overridden if the
    # actual CSV uses different header names.
    STREET_COL = "NOMBRE_VIA"
    ZONE_COL = "COD_SER"          # Preferred; alternatives tried if absent
    X_COL = "COORD_X_ETRS89"      # UTM Easting EPSG:25830
    Y_COL = "COORD_Y_ETRS89"      # UTM Northing EPSG:25830

    # Alternative zone column names to try if ZONE_COL is not found
    ZONE_COL_ALTERNATIVES = ["REGIMEN_SER", "TIPO_SER"]

    def __init__(self) -> None:
        # always_xy=True: transform(easting, northing) → (lng, lat)
        self._transformer = Transformer.from_crs(
            "EPSG:25830", "EPSG:4326", always_xy=True
        )
        self._headers_logged = False

    @classmethod
    def detect_columns(cls, headers: list[str]) -> dict[str, str | None]:
        """
        Try to map expected column roles to actual header names.

        Logs available headers at DEBUG level if expected columns are not found.
        Returns a dict of role → resolved_header (or None if not found).
        """
        upper_headers = {h.strip().upper(): h for h in headers}
        resolved: dict[str, str | None] = {}

        def _resolve(candidates: list[str]) -> str | None:
            for candidate in candidates:
                if candidate.upper() in upper_headers:
                    return upper_headers[candidate.upper()]
            return None

        resolved["street"] = _resolve([cls.STREET_COL])
        resolved["zone"] = _resolve([cls.ZONE_COL] + cls.ZONE_COL_ALTERNATIVES)
        resolved["x"] = _resolve([cls.X_COL])
        resolved["y"] = _resolve([cls.Y_COL])

        missing = [role for role, col in resolved.items() if col is None]
        if missing:
            logger.debug(
                "Expected columns not found for roles %s. Available headers: %s",
                missing,
                headers,
            )

        return resolved

    def parse(self, csv_text: str) -> tuple[list[SerZoneRecord], int]:
        """
        Parse CSV text.

        Returns (records, skipped_count).
        """
        reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")

        headers = reader.fieldnames or []
        if not self._headers_logged:
            logger.debug("CSV headers: %s", headers)
            self._headers_logged = True

        resolved = self.detect_columns(list(headers))
        street_col = resolved["street"]
        zone_col = resolved["zone"]
        x_col = resolved["x"]
        y_col = resolved["y"]

        if not all([street_col, zone_col, x_col, y_col]):
            logger.warning(
                "One or more required columns not found. "
                "Resolved: %s. Returning empty result.",
                resolved,
            )
            return [], 0

        records: list[SerZoneRecord] = []
        skipped = 0

        for row in reader:
            street = row.get(street_col, "").strip()  # type: ignore[arg-type]
            zone = row.get(zone_col, "").strip()  # type: ignore[arg-type]
            x_raw = row.get(x_col, "").strip()  # type: ignore[arg-type]
            y_raw = row.get(y_col, "").strip()  # type: ignore[arg-type]

            if not street or not zone or not x_raw or not y_raw:
                skipped += 1
                continue

            try:
                x = float(x_raw.replace(",", "."))
                y = float(y_raw.replace(",", "."))
            except ValueError:
                logger.warning(
                    "Invalid UTM coordinates for row (street=%r): x=%r y=%r",
                    street,
                    x_raw,
                    y_raw,
                )
                skipped += 1
                continue

            if math.isnan(x) or math.isnan(y):
                skipped += 1
                continue

            # Reproject: EPSG:25830 (UTM easting/northing) → EPSG:4326 (lng, lat)
            lng, lat = self._transformer.transform(x, y)

            # Validate Madrid bounding box
            if not (
                _MADRID_LAT_MIN <= lat <= _MADRID_LAT_MAX
                and _MADRID_LNG_MIN <= lng <= _MADRID_LNG_MAX
            ):
                skipped += 1
                continue

            zone_label = ZONE_LABELS.get(zone, zone)

            records.append(
                SerZoneRecord(
                    street_name=street,
                    zone_code=zone,
                    zone_label=zone_label,
                    latitude=lat,
                    longitude=lng,
                )
            )

        logger.info(
            "Parsed %d valid records, skipped %d rows", len(records), skipped
        )
        return records, skipped
