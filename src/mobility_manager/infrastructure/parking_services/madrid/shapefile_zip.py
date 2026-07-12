"""
Infrastructure: shared shapefile-zip download and in-memory extraction
helpers, used by both ser_band_shapefile.py and barrios_shapefile.py.

Both Madrid shapefile sources (SER bands, Barrios) are downloaded as a zip
archive from an allowlisted hostname and have their .shp/.dbf components
extracted entirely in memory (no permanent temp file) — this module factors
out that shared plumbing so each caller only supplies its own URL, allowed
hostnames, basename, and log/error message text. Each caller keeps its own
domain-specific field parsing (SerBand / BarrioRecord) unchanged.
"""

from __future__ import annotations

import io
import logging
import zipfile
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)


def hostname_allowed(url: str, allowed_hostnames: set[str]) -> None:
    """Raise ValueError if url's hostname is not in allowed_hostnames."""
    hostname = urlparse(url).hostname or ""
    if hostname not in allowed_hostnames:
        raise ValueError(f"URL hostname {hostname!r} is not in the allowed list: {allowed_hostnames}")


def fetch_zip(url: str, allowed_hostnames: set[str], *, source_label: str) -> bytes:
    """
    Download a zip archive from url after checking it against
    allowed_hostnames, and return its raw bytes.

    source_label is used only for log/error message text (e.g. "Madrid SER
    band shapefile zip", "Madrid Barrios shapefile zip") so each caller's
    existing messages are preserved verbatim.
    """
    hostname_allowed(url, allowed_hostnames)
    logger.info("Fetching %s from %s", source_label, url)
    with httpx.Client(follow_redirects=True, timeout=120.0) as client:
        response = client.get(url)

    if not response.is_success:
        raise RuntimeError(f"Failed to fetch {source_label}: HTTP {response.status_code}")

    logger.info("Fetched %s (%d bytes)", source_label, len(response.content))
    return response.content


def extract_shapefile_components(zip_bytes: bytes, basename: str, *, zip_label: str) -> tuple[io.BytesIO, io.BytesIO]:
    """
    Extract .shp and .dbf members matching basename from the zip, entirely
    in memory.

    zip_label is used only for the error message text (e.g. "SER band
    shapefile", "Barrios shapefile") so each caller's existing message is
    preserved verbatim.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as archive:
        shp_name = next(
            (n for n in archive.namelist() if n.lower().endswith(f"{basename.lower()}.shp")),
            None,
        )
        dbf_name = next(
            (n for n in archive.namelist() if n.lower().endswith(f"{basename.lower()}.dbf")),
            None,
        )
        if shp_name is None or dbf_name is None:
            raise RuntimeError(f"{zip_label} zip did not contain {basename}.shp/.dbf; found: {archive.namelist()}")
        shp_bytes = io.BytesIO(archive.read(shp_name))
        dbf_bytes = io.BytesIO(archive.read(dbf_name))
    return shp_bytes, dbf_bytes
