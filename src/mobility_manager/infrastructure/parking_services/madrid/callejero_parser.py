"""
Infrastructure: Madrid callejero CSV parsing.

Parses the Madrid "callejero" (street directory) CSV — dataset 200075 — used
here solely as a source of administrative `zone_number`, street name, and
district per address point. Coordinates are published as WGS84 DMS strings
and are converted to decimal degrees, then reprojected to EPSG:25830 so they
can be spatially joined against the SER band shapefile (see design.md D3).

Also captures `Codigo de distrito`/`Codigo de barrio` — previously-unused
numeric codes needed to resolve each zone_number's frontier via a
compound-code lookup against the Barrios shapefile (see
add-ser-zone-frontiers design.md D2). These codes are zero-padded strings in
the real CSV (e.g. "01", "06") — callers that build a Barrios-style compound
key (e.g. "1-6") must strip leading zeros first; this module deliberately
does not normalize them, keeping them verbatim as parsed from the source.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from dataclasses import dataclass

from pyproj import Transformer

logger = logging.getLogger(__name__)

# Reproject WGS84 EPSG:4326 -> UTM EPSG:25830 (same pattern as domain/value_objects/location.py)
_wgs84_to_utm = Transformer.from_crs("EPSG:4326", "EPSG:25830", always_xy=True)

# DMS format seen in the source, e.g. 3º42'14.2'' W or 3°42'14.2'' W.
# The degree symbol is inconsistently either "º" (masculine ordinal indicator)
# or "°" (degree sign) across rows — both are tolerated.
_DMS_RE = re.compile(
    r"""
    \s*(?P<deg>\d+(?:\.\d+)?)\s*[ºo°]
    \s*(?P<min>\d+(?:\.\d+)?)\s*'
    \s*(?P<sec>\d+(?:\.\d+)?)\s*''
    \s*(?P<hemi>[NSEW])\s*
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class CallejeroPoint:
    """One parsed callejero address point."""

    zone_number: str
    street_name: str
    district: str
    district_code: str  # "Codigo de distrito", e.g. "01" — zero-padded in the source CSV
    barrio_code: str  # "Codigo de barrio", e.g. "06" — zero-padded in the source CSV
    lat: float  # WGS84
    lng: float  # WGS84
    utm_x: float  # EPSG:25830 easting
    utm_y: float  # EPSG:25830 northing


def parse_dms(raw: str) -> float | None:
    """
    Convert a DMS coordinate string (e.g. "3º42'14.2'' W") to decimal degrees.

    Tolerant of both "º" and "°" degree-symbol variants. Returns None if the
    string cannot be parsed.
    """
    if not raw:
        return None
    match = _DMS_RE.match(raw.strip())
    if match is None:
        return None

    degrees = float(match.group("deg"))
    minutes = float(match.group("min"))
    seconds = float(match.group("sec"))
    hemisphere = match.group("hemi")

    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if hemisphere in ("S", "W"):
        decimal = -decimal
    return decimal


def parse_callejero_csv(csv_text: str) -> list[CallejeroPoint]:
    """
    Parse the Madrid callejero CSV into a list of CallejeroPoint.

    The CSV is semicolon-delimited. Rows missing mandatory fields or with
    unparseable coordinates are skipped.
    """
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
    points: list[CallejeroPoint] = []
    skipped = 0

    for row_num, row in enumerate(reader, start=2):
        street_name = (row.get("Nombre de la vía") or "").strip()
        zone_number = (row.get("Zona Servicio Estacionamiento Regulado") or "").strip()
        district = (row.get("Nombre del distrito") or "").strip()
        district_code = (row.get("Codigo de distrito") or "").strip()
        barrio_code = (row.get("Codigo de barrio") or "").strip()
        raw_lng = (row.get("Longitud en S R  ETRS89 WGS84") or "").strip()
        raw_lat = (row.get("Latitud en S R  ETRS89 WGS84") or "").strip()

        if not street_name or not zone_number or not raw_lng or not raw_lat:
            skipped += 1
            continue

        if zone_number == "000":
            # "000" is Madrid's callejero code meaning this address is NOT
            # part of any SER zone — it must not be usable as a spatial-join
            # target, or real SER bands snap to it instead of the correct
            # zoned address (see design.md D3 / bugfix in
            # add-ser-zone-boundaries).
            skipped += 1
            continue

        lng = parse_dms(raw_lng)
        lat = parse_dms(raw_lat)
        if lng is None or lat is None:
            logger.debug("Row %d: skipping — unparseable DMS coordinates", row_num)
            skipped += 1
            continue

        utm_x, utm_y = _wgs84_to_utm.transform(lng, lat)

        points.append(
            CallejeroPoint(
                zone_number=zone_number,
                street_name=street_name,
                district=district,
                district_code=district_code,
                barrio_code=barrio_code,
                lat=lat,
                lng=lng,
                utm_x=utm_x,
                utm_y=utm_y,
            )
        )

    logger.info(
        "Parsed Madrid callejero CSV: %d points kept, %d skipped",
        len(points),
        skipped,
    )
    return points
