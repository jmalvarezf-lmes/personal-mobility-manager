"""
Infrastructure: MadridSerStreetsProvider.

Combines the Madrid SER band shapefile (curb-band polylines) and the
callejero CSV (administrative zone/street/district per address point) into
zone-boundary records: download both sources, parse, spatially join,
buffer + dissolve. Replaces the retired MadridSerCallesProvider, which
fetched a single point-based CSV (see design.md D2 of add-ser-zone-boundaries).

get_zone_areas() additionally downloads and parses the Madrid Barrios
shapefile (a third Madrid source) and resolves one presentation-only
frontier per zone_number via a compound-code majority-vote lookup — see
design.md D1/D2/D7 of add-ser-zone-frontiers. Per D7, get_records() and
get_zone_areas() share no cross-call cache: each independently re-downloads
and re-parses everything it needs from scratch on every call.
"""

import logging

from mobility_manager.domain.ports.city_parking_data_provider import (
    CityParkingDataProvider,
)
from mobility_manager.domain.value_objects.ser_zone_boundary_record import (
    SerZoneBoundaryRecord,
)
from mobility_manager.domain.value_objects.zone_area import ZoneArea
from mobility_manager.infrastructure.parking_services.madrid.barrios_shapefile import (
    download_and_parse_barrios,
)
from mobility_manager.infrastructure.parking_services.madrid.buffer_dissolve import (
    buffer_and_dissolve,
)
from mobility_manager.infrastructure.parking_services.madrid.callejero_parser import (
    parse_callejero_csv,
)
from mobility_manager.infrastructure.parking_services.madrid.data_fetcher import (
    MadridCallejeroCsvFetcher,
)
from mobility_manager.infrastructure.parking_services.madrid.ser_band_shapefile import (
    download_and_parse_ser_bands,
)
from mobility_manager.infrastructure.parking_services.madrid.spatial_join import (
    join_bands_to_callejero,
)
from mobility_manager.infrastructure.parking_services.madrid.zone_area_resolver import (
    resolve_zone_areas,
)

logger = logging.getLogger(__name__)

DEFAULT_SER_ZONE_SHP_URL = "https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/MOVILIDAD/ZONA_SER/SHP_ZIP.zip"
DEFAULT_MADRID_CALLEJERO_URL = (
    "https://datos.madrid.es/dataset/200075-0-callejero/resource/"
    "200075-1-callejero-csv/download/200075-1-callejero-csv.csv"
)
DEFAULT_MADRID_BARRIOS_SHP_URL = (
    "https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/LIMITES_ADMINISTRATIVOS/Barrios/Barrios.zip"
)


class MadridSerStreetsProvider(CityParkingDataProvider):
    """Provides Madrid SER zone boundary records from combined Open Data sources."""

    def __init__(
        self,
        shp_url: str = DEFAULT_SER_ZONE_SHP_URL,
        callejero_url: str = DEFAULT_MADRID_CALLEJERO_URL,
        barrios_shp_url: str = DEFAULT_MADRID_BARRIOS_SHP_URL,
    ) -> None:
        self._shp_url = shp_url
        self._callejero_url = callejero_url
        self._barrios_shp_url = barrios_shp_url
        # Reuses the existing hostname-allowlist pattern (datos.madrid.es) via
        # MadridCallejeroCsvFetcher's constructor validation.
        self._callejero_fetcher = MadridCallejeroCsvFetcher(url=callejero_url)

    @property
    def city_code(self) -> str:
        return "madrid"

    def get_records(self) -> list[SerZoneBoundaryRecord]:
        """
        Fetch and combine both Madrid sources into zone boundary records.

        Raises an exception if either source fails to download or parse.
        """
        bands = download_and_parse_ser_bands(self._shp_url)
        callejero_csv = self._callejero_fetcher.fetch()
        callejero_points = parse_callejero_csv(callejero_csv)

        joined = join_bands_to_callejero(bands, callejero_points)
        records = buffer_and_dissolve(joined)

        logger.info(
            "MadridSerStreetsProvider.get_records(): %d bands, %d callejero points, %d zone boundary records",
            len(bands),
            len(callejero_points),
            len(records),
        )
        return records

    def get_zone_areas(self) -> list[ZoneArea]:
        """
        Fetch and resolve one presentation-only frontier (ZoneArea) per
        resolvable zone_number.

        Re-downloads and re-parses the SER band shapefile, callejero CSV,
        and Barrios shapefile independently of get_records() — no
        cross-call cache is shared between the two methods (design.md D7).
        Raises an exception if any of the three sources fails to download or
        parse.
        """
        bands = download_and_parse_ser_bands(self._shp_url)
        callejero_csv = self._callejero_fetcher.fetch()
        callejero_points = parse_callejero_csv(callejero_csv)
        joined = join_bands_to_callejero(bands, callejero_points)

        barrio_records = download_and_parse_barrios(self._barrios_shp_url)
        zone_areas = resolve_zone_areas(joined, barrio_records)

        logger.info(
            "MadridSerStreetsProvider.get_zone_areas(): %d bands, %d barrio records, %d zone areas resolved",
            len(bands),
            len(barrio_records),
            len(zone_areas),
        )
        return zone_areas
