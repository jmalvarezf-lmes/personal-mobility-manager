"""
Infrastructure: Madrid Barrios (neighbourhood) shapefile download and parsing.

Downloads the MADRID_BARRIOS_SHP_URL zip archive, extracts the BARRIOS
shapefile components in memory (no permanent temp file), and parses each of
the 131 official neighbourhood boundary records. Mirrors the structure of
ser_band_shapefile.py — see design.md D1 of add-ser-zone-frontiers.
"""

from __future__ import annotations

import io
import logging
from dataclasses import dataclass

import shapefile
from shapely.geometry import shape as shapely_shape
from shapely.geometry.base import BaseGeometry

from mobility_manager.infrastructure.parking_services.madrid.shapefile_zip import (
    extract_shapefile_components,
    fetch_zip,
)

logger = logging.getLogger(__name__)

_ALLOWED_HOSTNAMES = {"geoportal.madrid.es"}

_SHAPEFILE_BASENAME = "BARRIOS"


@dataclass(frozen=True)
class BarrioRecord:
    """One parsed Barrios (neighbourhood) administrative boundary record."""

    cod_disb: str  # compound district-barrio code, e.g. "1-1"
    nombre: str  # official barrio name, e.g. "Palacio"
    geometry: BaseGeometry  # Polygon or MultiPolygon, EPSG:25830 metres


def fetch_barrios_zip(url: str) -> bytes:
    """Download the Barrios shapefile zip archive and return its raw bytes."""
    return fetch_zip(url, _ALLOWED_HOSTNAMES, source_label="Madrid Barrios shapefile zip")


def _extract_shapefile_components(zip_bytes: bytes) -> tuple[io.BytesIO, io.BytesIO]:
    """
    Extract .shp and .dbf members matching BARRIOS from the zip, entirely in
    memory.
    """
    return extract_shapefile_components(zip_bytes, _SHAPEFILE_BASENAME, zip_label="Barrios shapefile")


def parse_barrios(shp_bytes: io.BytesIO, dbf_bytes: io.BytesIO) -> list[BarrioRecord]:
    """
    Parse Barrios records from in-memory .shp/.dbf streams.

    Records with a missing/blank COD_DISB or NOMBRE, or degenerate geometry,
    are skipped with a warning rather than raising — consistent with the
    project's existing "skip the bad item, log a warning, keep going"
    convention (see design.md D5).
    """
    reader = shapefile.Reader(shp=shp_bytes, dbf=dbf_bytes)
    records: list[BarrioRecord] = []
    skipped = 0

    for shape_record in reader.iterShapeRecords():
        record = shape_record.record.as_dict()
        cod_disb = str(record.get("COD_DISB") or "").strip()
        nombre = str(record.get("NOMBRE") or "").strip()

        if not cod_disb or not nombre:
            logger.warning("Skipping Barrios record — missing COD_DISB or NOMBRE: %r", record)
            skipped += 1
            continue

        geo_interface = shape_record.shape.__geo_interface__
        if not geo_interface or not geo_interface.get("coordinates"):
            logger.warning("Skipping Barrios record %r — degenerate geometry", cod_disb)
            skipped += 1
            continue

        geometry = shapely_shape(geo_interface)

        records.append(
            BarrioRecord(
                cod_disb=cod_disb,
                nombre=nombre,
                geometry=geometry,
            )
        )

    logger.info(
        "Parsed Madrid Barrios shapefile: %d records kept, %d skipped",
        len(records),
        skipped,
    )
    return records


def download_and_parse_barrios(url: str) -> list[BarrioRecord]:
    """Fetch, unzip, and parse the Barrios shapefile end to end."""
    zip_bytes = fetch_barrios_zip(url)
    shp_bytes, dbf_bytes = _extract_shapefile_components(zip_bytes)
    return parse_barrios(shp_bytes, dbf_bytes)
