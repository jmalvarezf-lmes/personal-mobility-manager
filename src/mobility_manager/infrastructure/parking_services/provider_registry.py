"""
Infrastructure: CityParkingDataProvider registry.

Reads the ENABLED_CITIES env var (comma-separated, default "madrid") and
returns one provider instance per configured city. Unknown city codes are
logged as a warning and ignored.
"""

import logging
import os

from mobility_manager.domain.ports.city_parking_data_provider import (
    CityParkingDataProvider,
)
from mobility_manager.infrastructure.parking_services.madrid.ser_calles_provider import (
    MadridSerCallesProvider,
)

logger = logging.getLogger(__name__)

_DEFAULT_MADRID_SER_CALLES_URL = (
    "https://datos.madrid.es/dataset/218228-0-ser-calles/resource/"
    "218228-1-ser-calles-csv/download/218228-1-ser-calles-csv.csv"
)

_KNOWN_CITIES: set[str] = {"madrid"}


def build_providers() -> list[CityParkingDataProvider]:
    """
    Return a provider instance for each city listed in ENABLED_CITIES.

    ENABLED_CITIES defaults to "madrid" if unset.
    """
    raw = os.environ.get("ENABLED_CITIES", "madrid")
    city_codes = [c.strip().lower() for c in raw.split(",") if c.strip()]

    providers: list[CityParkingDataProvider] = []
    for code in city_codes:
        if code == "madrid":
            url = os.environ.get("MADRID_SER_CALLES_URL", _DEFAULT_MADRID_SER_CALLES_URL)
            providers.append(MadridSerCallesProvider(url=url))
        else:
            logger.warning("ENABLED_CITIES contains unknown city code %r — skipping", code)

    if not providers:
        logger.warning("No valid city providers configured. ENABLED_CITIES=%r", raw)

    return providers
