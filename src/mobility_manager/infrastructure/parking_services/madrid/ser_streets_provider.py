"""
Infrastructure: MadridSerStreetsProvider.

Combines the Madrid SER band shapefile (curb-band polylines) and the
callejero CSV (administrative zone/street/district per address point) into
zone-boundary records: download both sources, parse, spatially join,
buffer + dissolve. Replaces the retired MadridSerCallesProvider, which
fetched a single point-based CSV (see design.md D2).
"""

import logging

from mobility_manager.domain.ports.city_parking_data_provider import (
    CityParkingDataProvider,
)
from mobility_manager.domain.value_objects.ser_zone_boundary_record import (
    SerZoneBoundaryRecord,
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

logger = logging.getLogger(__name__)

DEFAULT_SER_ZONE_SHP_URL = "https://geoportal.madrid.es/fsdescargas/IDEAM_WBGEOPORTAL/MOVILIDAD/ZONA_SER/SHP_ZIP.zip"
DEFAULT_MADRID_CALLEJERO_URL = (
    "https://datos.madrid.es/dataset/200075-0-callejero/resource/"
    "200075-1-callejero-csv/download/200075-1-callejero-csv.csv"
)


class MadridSerStreetsProvider(CityParkingDataProvider):
    """Provides Madrid SER zone boundary records from two combined Open Data sources."""

    def __init__(
        self,
        shp_url: str = DEFAULT_SER_ZONE_SHP_URL,
        callejero_url: str = DEFAULT_MADRID_CALLEJERO_URL,
    ) -> None:
        self._shp_url = shp_url
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
