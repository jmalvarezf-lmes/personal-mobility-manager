"""
Infrastructure: Madrid SER band shapefile download and parsing.

Downloads the SER_ZONE_SHP_URL zip archive, extracts the
SER_BANDA_APARCAMIENTO shapefile components in memory (no permanent temp
file), and parses each curb-band polyline record. `Bateria_Li` (parking
orientation) exists in the real file but is deliberately not parsed — see
design.md D4.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import shapefile
import shapely
from shapely.geometry import LineString

from mobility_manager.infrastructure.parking_services.madrid.shapefile_zip import (
    extract_shapefile_components,
    fetch_zip,
)
from mobility_manager.infrastructure.parking_services.madrid.zone_type import (
    MadridZoneType,
)

logger = logging.getLogger(__name__)

_ALLOWED_HOSTNAMES = {"geoportal.madrid.es"}

_SHAPEFILE_BASENAME = "SER_BANDA_APARCAMIENTO"

_GRIS = "Gris"


@dataclass(frozen=True)
class SerBand:
    """One parsed SER curb-band record (before spatial join / buffering)."""

    zone_type: str  # validated MadridZoneType.display_name
    spot_count: int  # -1 means unknown
    geometry: LineString


def fetch_ser_band_zip(url: str) -> bytes:
    """Download the SER band shapefile zip archive and return its raw bytes."""
    return fetch_zip(url, _ALLOWED_HOSTNAMES, source_label="Madrid SER band shapefile zip")


def _extract_shapefile_components(zip_bytes: bytes) -> tuple[io.BytesIO, io.BytesIO]:
    """
    Extract .shp and .dbf members matching SER_BANDA_APARCAMIENTO from the zip,
    entirely in memory.
    """
    return extract_shapefile_components(zip_bytes, _SHAPEFILE_BASENAME, zip_label="SER band shapefile")


def parse_ser_bands(shp_bytes: io.BytesIO, dbf_bytes: io.BytesIO) -> list[SerBand]:
    """
    Parse SER band records from in-memory .shp/.dbf streams.

    Bands with Color == "Gris" are discarded. Bands with an unrecognised
    Color are skipped with a warning + counter.
    """
    reader = shapefile.Reader(shp=shp_bytes, dbf=dbf_bytes)
    bands: list[SerBand] = []
    skipped_gris = 0
    skipped_unrecognised = 0

    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        raw_color = str(record.get("Color") or "").strip()

        if raw_color == _GRIS:
            skipped_gris += 1
            continue

        zone_type = MadridZoneType.from_raw(raw_color)
        if zone_type is None:
            logger.warning("Skipping SER band — unrecognised Color %r", raw_color)
            skipped_unrecognised += 1
            continue

        spot_count = _parse_spot_count(record.get("Res_NumPla"))

        points = shape_record.shape.points
        if len(points) < 2:
            logger.debug("Skipping SER band — degenerate geometry with %d point(s)", len(points))
            skipped_unrecognised += 1
            continue

        geometry = shapely.LineString(points)

        bands.append(
            SerBand(
                zone_type=zone_type.display_name,
                spot_count=spot_count,
                geometry=geometry,
            )
        )

    logger.info(
        "Parsed SER band shapefile: %d bands kept, %d Gris skipped, %d unrecognised/invalid skipped",
        len(bands),
        skipped_gris,
        skipped_unrecognised,
    )
    return bands


def _parse_spot_count(raw: object) -> int:
    """Return the spot count, or -1 if absent/non-numeric."""
    if isinstance(raw, int):
        return raw
    if isinstance(raw, float):
        return int(raw)
    if isinstance(raw, str):
        try:
            return int(raw)
        except ValueError:
            return -1
    return -1


def download_and_parse_ser_bands(url: str) -> list[SerBand]:
    """Fetch, unzip, and parse the SER band shapefile end to end."""
    zip_bytes = fetch_ser_band_zip(url)
    shp_bytes, dbf_bytes = _extract_shapefile_components(zip_bytes)
    return parse_ser_bands(shp_bytes, dbf_bytes)
