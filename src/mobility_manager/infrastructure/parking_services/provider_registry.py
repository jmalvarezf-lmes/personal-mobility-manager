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
from mobility_manager.infrastructure.parking_services.madrid.ser_streets_provider import (
    DEFAULT_MADRID_CALLEJERO_URL,
    DEFAULT_SER_ZONE_SHP_URL,
    MadridSerStreetsProvider,
)

logger = logging.getLogger(__name__)

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
            shp_url = os.environ.get("SER_ZONE_SHP_URL", DEFAULT_SER_ZONE_SHP_URL)
            callejero_url = os.environ.get("MADRID_CALLEJERO_URL", DEFAULT_MADRID_CALLEJERO_URL)
            providers.append(MadridSerStreetsProvider(shp_url=shp_url, callejero_url=callejero_url))
        else:
            logger.warning("ENABLED_CITIES contains unknown city code %r — skipping", code)

    if not providers:
        logger.warning("No valid city providers configured. ENABLED_CITIES=%r", raw)

    return providers
