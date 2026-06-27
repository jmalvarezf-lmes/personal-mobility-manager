"""
Infrastructure: MadridSerCallesProvider.

Fetches, parses, and validates parking spot records from the Madrid SER
Calles CSV dataset (dataset 218228). This replaces the previous two-step
callejero fetcher + parser pipeline with a single self-contained provider.
"""
import csv
import io
import logging
from urllib.parse import urlparse

import httpx
from pyproj import Transformer

from mobility_manager.domain.ports.city_parking_data_provider import (
    CityParkingDataProvider,
)
from mobility_manager.domain.value_objects.parking_spot_record import ParkingSpotRecord
from mobility_manager.infrastructure.parking_services.madrid.zone_type import (
    MadridZoneType,
)

logger = logging.getLogger(__name__)

_ALLOWED_HOSTNAMES = {"datos.madrid.es"}

_DEFAULT_URL = (
    "https://datos.madrid.es/dataset/218228-0-ser-calles/resource/"
    "218228-1-ser-calles-csv/download/218228-1-ser-calles-csv.csv"
)

# Madrid bounding box (WGS84) — reject obviously out-of-range coordinates
_LAT_MIN, _LAT_MAX = 40.3, 40.6
_LON_MIN, _LON_MAX = -3.8, -3.6

# Reproject UTM EPSG:25830 → WGS84 EPSG:4326
_utm_to_wgs84 = Transformer.from_crs("EPSG:25830", "EPSG:4326", always_xy=True)


class MadridSerCallesProvider(CityParkingDataProvider):
    """Provides Madrid SER parking spot records from the 218228 Open Data CSV."""

    def __init__(self, url: str = _DEFAULT_URL) -> None:
        hostname = urlparse(url).hostname or ""
        if hostname not in _ALLOWED_HOSTNAMES:
            raise ValueError(
                f"URL hostname {hostname!r} is not in the allowed list: {_ALLOWED_HOSTNAMES}"
            )
        self._url = url

    @property
    def city_code(self) -> str:
        return "madrid"

    def get_records(self) -> list[ParkingSpotRecord]:
        """
        Fetch the Madrid SER Calles CSV and return validated parking spot records.

        Rows with unrecognised zone types are skipped with a warning.
        Rows missing mandatory fields (calle, color, gis_x, gis_y) are skipped.
        Rows with out-of-range coordinates are skipped.
        Missing/non-numeric numero_plazas yields spot_count = -1 (row not skipped).
        """
        csv_text = self._fetch()
        return self._parse(csv_text)

    def _fetch(self) -> str:
        logger.info("Fetching Madrid SER Calles CSV from %s", self._url)
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            response = client.get(self._url)

        if not response.is_success:
            raise RuntimeError(
                f"Failed to fetch Madrid SER Calles CSV: HTTP {response.status_code}"
            )

        logger.info("Fetched Madrid SER Calles CSV (%d bytes)", len(response.content))
        return response.content.decode("latin-1")

    def _parse(self, csv_text: str) -> list[ParkingSpotRecord]:
        reader = csv.DictReader(io.StringIO(csv_text), delimiter=";")
        records: list[ParkingSpotRecord] = []
        skipped_zone = 0
        skipped_missing = 0
        skipped_coords = 0

        for row_num, row in enumerate(reader, start=2):
            calle = (row.get("calle") or "").strip()
            raw_color = (row.get("color") or "").strip()
            raw_x = (row.get("gis_x") or "").strip()
            raw_y = (row.get("gis_y") or "").strip()

            if not calle or not raw_color or not raw_x or not raw_y:
                logger.debug("Row %d: skipping — missing mandatory field(s)", row_num)
                skipped_missing += 1
                continue

            zone_name = self._parse_zone_name(raw_color)
            if zone_name is None:
                logger.warning(
                    "Row %d: skipping — unrecognised zone type %r (full field: %r)",
                    row_num,
                    raw_color.split(" ", 1)[1] if " " in raw_color else raw_color,
                    raw_color,
                )
                skipped_zone += 1
                continue

            try:
                utm_x = float(raw_x)
                utm_y = float(raw_y)
            except ValueError:
                logger.debug(
                    "Row %d: skipping — non-numeric coordinates x=%r y=%r",
                    row_num,
                    raw_x,
                    raw_y,
                )
                skipped_missing += 1
                continue

            lon, lat = _utm_to_wgs84.transform(utm_x, utm_y)

            if not (_LAT_MIN <= lat <= _LAT_MAX and _LON_MIN <= lon <= _LON_MAX):
                logger.debug(
                    "Row %d: skipping — coordinates outside Madrid bbox (lat=%f, lon=%f)",
                    row_num,
                    lat,
                    lon,
                )
                skipped_coords += 1
                continue

            spot_count = self._parse_spot_count(row.get("numero_plazas") or "")

            records.append(
                ParkingSpotRecord(
                    street_name=calle,
                    zone_type=zone_name,
                    latitude=lat,
                    longitude=lon,
                    utm_x=utm_x,
                    utm_y=utm_y,
                    spot_count=spot_count,
                )
            )

        logger.info(
            "Parsed Madrid SER Calles CSV: %d records kept, %d skipped "
            "(zone=%d, missing=%d, coords=%d)",
            len(records),
            skipped_zone + skipped_missing + skipped_coords,
            skipped_zone,
            skipped_missing,
            skipped_coords,
        )
        return records

    @staticmethod
    def _parse_zone_name(raw_color: str) -> str | None:
        """
        Extract the plain zone type name from the raw CSV color field.

        The field format is "<9-digit-RGB-prefix> <name>", e.g.:
            "043000255 Azul"  →  "Azul"
            "081209246 Alta Rotación"  →  "Alta Rotación"

        After stripping the prefix, the plain name is validated against
        MadridZoneType. Returns None for unrecognised names.
        """
        if " " in raw_color:
            plain = raw_color.split(" ", 1)[1].strip()
        else:
            plain = raw_color

        zone_type = MadridZoneType.from_raw(plain)
        return zone_type.display_name if zone_type is not None else None

    @staticmethod
    def _parse_spot_count(raw: str) -> int:
        """Return the spot count, or -1 if the field is absent/empty/non-numeric."""
        raw = raw.strip()
        if not raw:
            return -1
        try:
            return int(raw)
        except ValueError:
            return -1
