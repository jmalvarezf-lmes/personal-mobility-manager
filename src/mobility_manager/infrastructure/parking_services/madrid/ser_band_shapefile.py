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
import zipfile
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
import shapefile
import shapely
from shapely.geometry import LineString

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


def _hostname_allowed(url: str) -> None:
    hostname = urlparse(url).hostname or ""
    if hostname not in _ALLOWED_HOSTNAMES:
        raise ValueError(f"URL hostname {hostname!r} is not in the allowed list: {_ALLOWED_HOSTNAMES}")


def fetch_ser_band_zip(url: str) -> bytes:
    """Download the SER band shapefile zip archive and return its raw bytes."""
    _hostname_allowed(url)
    logger.info("Fetching Madrid SER band shapefile zip from %s", url)
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        response = client.get(url)

    if not response.is_success:
        raise RuntimeError(f"Failed to fetch Madrid SER band shapefile zip: HTTP {response.status_code}")

    logger.info("Fetched Madrid SER band shapefile zip (%d bytes)", len(response.content))
    return response.content


def _extract_shapefile_components(zip_bytes: bytes) -> tuple[io.BytesIO, io.BytesIO]:
    """
    Extract .shp and .dbf members matching SER_BANDA_APARCAMIENTO from the zip,
    entirely in memory.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        shp_name = next(
            (n for n in archive.namelist() if n.lower().endswith(f"{_SHAPEFILE_BASENAME.lower()}.shp")),
            None,
        )
        dbf_name = next(
            (n for n in archive.namelist() if n.lower().endswith(f"{_SHAPEFILE_BASENAME.lower()}.dbf")),
            None,
        )
        if shp_name is None or dbf_name is None:
            raise RuntimeError(
                f"SER band shapefile zip did not contain {_SHAPEFILE_BASENAME}.shp/.dbf; found: {archive.namelist()}"
            )
        shp_bytes = io.BytesIO(archive.read(shp_name))
        dbf_bytes = io.BytesIO(archive.read(dbf_name))
    return shp_bytes, dbf_bytes


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
