"""
Infrastructure: CityParkingDataProvider registry.

Queries the `cities` table for all registered city codes and returns one
provider instance per code that has a matching implementation registered
in code. A `cities` row with no matching implementation is logged as a
warning and skipped — the `cities` table is the sole source of truth for
which city codes are active (see add-ser-enforcement-calendar design.md
D10).
"""

import logging
import os

from sqlalchemy import text
from sqlalchemy.engine import Engine

from mobility_manager.domain.ports.city_parking_data_provider import (
    CityParkingDataProvider,
)
from mobility_manager.infrastructure.parking_services.madrid.ser_streets_provider import (
    DEFAULT_MADRID_BARRIOS_SHP_URL,
    DEFAULT_MADRID_CALLEJERO_URL,
    DEFAULT_SER_ZONE_SHP_URL,
    MadridSerStreetsProvider,
)

logger = logging.getLogger(__name__)


def list_city_codes(engine: Engine) -> list[str]:
    """
    Return every city code registered in the `cities` table.

    Shared by `build_providers()` (below) and app.py's public-holiday-refresh
    wiring, which needs the full set of registered cities independent of
    whether each one has an implemented parking-data provider (see
    add-ser-enforcement-calendar design.md D7).
    """
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT code FROM cities")).fetchall()
    return [row[0] for row in rows]


def build_providers(engine: Engine) -> list[CityParkingDataProvider]:
    """
    Return a provider instance for each city code registered in `cities`.

    For each `code` returned by `SELECT code FROM cities`, constructs the
    matching provider if one is registered in code (only `code == "madrid"`
    today); any other `code` has no implementation and is logged as a
    warning and skipped, rather than crashing startup.
    """
    city_codes = list_city_codes(engine)

    providers: list[CityParkingDataProvider] = []
    for code in city_codes:
        if code == "madrid":
            shp_url = os.environ.get("SER_ZONE_SHP_URL", DEFAULT_SER_ZONE_SHP_URL)
            callejero_url = os.environ.get("MADRID_CALLEJERO_URL", DEFAULT_MADRID_CALLEJERO_URL)
            barrios_shp_url = os.environ.get("MADRID_BARRIOS_SHP_URL", DEFAULT_MADRID_BARRIOS_SHP_URL)
            providers.append(
                MadridSerStreetsProvider(
                    shp_url=shp_url,
                    callejero_url=callejero_url,
                    barrios_shp_url=barrios_shp_url,
                )
            )
        else:
            logger.warning("cities table contains code %r with no registered provider implementation — skipping", code)

    if not providers:
        logger.warning("No valid city providers configured. cities table codes: %r", city_codes)

    return providers
