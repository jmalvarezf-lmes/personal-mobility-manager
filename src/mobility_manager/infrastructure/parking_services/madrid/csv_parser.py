"""
Infrastructure: CallejeroCsvParser.

Parses the Madrid Callejero CSV (200075-1-callejero-csv.csv), extracts street
names, SER zone codes, and UTM coordinates in EPSG:25830 (metres), then
reprojects to WGS84 (EPSG:4326) for bounding-box storage.

Coordinate columns in the real file are in centimetres; dividing by 100 gives
EPSG:25830 metre values directly usable for Euclidean distance calculation.
"""
import csv
import io
import logging
import math
import unicodedata
from dataclasses import dataclass

from pyproj import Transformer

logger = logging.getLogger(__name__)

# Madrid bounding box (WGS84) — records outside this box are discarded.
_MADRID_LAT_MIN = 39.8
_MADRID_LAT_MAX = 41.2
_MADRID_LNG_MIN = -4.6
_MADRID_LNG_MAX = -2.9


def _norm(s: str) -> str:
    """Strip accents and uppercase for accent-insensitive header matching."""
    return (
        unicodedata.normalize("NFKD", s)
        .encode("ASCII", "ignore")
        .decode()
        .upper()
    )


@dataclass
class SerZoneRecord:
    street_name: str
    zone_code: str
    zone_label: str
    latitude: float   # WGS84 — stored for bounding-box index
    longitude: float  # WGS84 — stored for bounding-box index
    utm_x: float      # EPSG:25830 easting (metres) — used for Euclidean distance
    utm_y: float      # EPSG:25830 northing (metres) — used for Euclidean distance


class CallejeroCsvParser:
    """Parses the Madrid Callejero CSV and reprojects coordinates to WGS84."""

    # Exact column names from 200075-1-callejero-csv.csv (semicolon-delimited, quoted).
    STREET_COL = "Nombre de la vía"
    ZONE_COL = "Zona Servicio Estacionamiento Regulado"
    X_COL = "Coordenada X (Guia Urbana) cm"   # UTM easting, EPSG:25830, centimetres
    Y_COL = "Coordenada Y (Guia Urbana) cm"   # UTM northing, EPSG:25830, centimetres

    # Zone code indicating no SER zone assigned — skip these rows.
    _NO_ZONE = "000"

    def __init__(self) -> None:
        # always_xy=True: transform(easting, northing) → (lng, lat)
        self._transformer = Transformer.from_crs(
            "EPSG:25830", "EPSG:4326", always_xy=True
        )
        self._headers_logged = False

    @classmethod
    def detect_columns(cls, headers: list[str]) -> dict[str, str | None]:
        """
        Map expected column roles to actual header names using accent-insensitive matching.

        Returns a dict of role → resolved_header (or None if not found).
        """
        norm_to_raw = {_norm(h.strip()): h for h in headers}

        def _resolve(candidates: list[str]) -> str | None:
            for candidate in candidates:
                key = _norm(candidate)
                if key in norm_to_raw:
                    return norm_to_raw[key]
            return None

        resolved: dict[str, str | None] = {
            "street": _resolve([cls.STREET_COL]),
            "zone": _resolve([cls.ZONE_COL]),
            "x": _resolve([cls.X_COL]),
            "y": _resolve([cls.Y_COL]),
        }

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

        Returns (records, skipped_count). Rows with zone code "000" (no SER
        zone assigned) are counted as skipped.
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

            # "000" means no SER zone is assigned to this address.
            if zone == self._NO_ZONE:
                skipped += 1
                continue

            try:
                # Coordinates are in centimetres; divide by 100 for metres.
                utm_x = float(x_raw) / 100.0
                utm_y = float(y_raw) / 100.0
            except ValueError:
                logger.warning(
                    "Invalid UTM coordinates for row (street=%r): x=%r y=%r",
                    street,
                    x_raw,
                    y_raw,
                )
                skipped += 1
                continue

            if math.isnan(utm_x) or math.isnan(utm_y):
                skipped += 1
                continue

            # Reproject: EPSG:25830 (UTM easting/northing, metres) → EPSG:4326 (lng, lat)
            lng, lat = self._transformer.transform(utm_x, utm_y)

            # Validate Madrid bounding box
            if not (
                _MADRID_LAT_MIN <= lat <= _MADRID_LAT_MAX
                and _MADRID_LNG_MIN <= lng <= _MADRID_LNG_MAX
            ):
                skipped += 1
                continue

            records.append(
                SerZoneRecord(
                    street_name=street,
                    zone_code=zone,
                    zone_label=zone,  # numeric SER codes have no colour mapping; code is the label
                    latitude=lat,
                    longitude=lng,
                    utm_x=utm_x,
                    utm_y=utm_y,
                )
            )

        logger.info(
            "Parsed %d valid records, skipped %d rows", len(records), skipped
        )
        return records, skipped
