"""
Infrastructure: SerTicketProviderRegistry.

Mirrors infrastructure/vehicle_providers/brand_registry.py's shape: a
registry class returning the currently available SerTicketProviderPort
implementations, keyed by provider name.

Reads ENABLED_SER_PROVIDERS env var (comma-separated, default "elparking")
directly — self-contained parsing, mirroring BrandRegistry.build_pull_providers()'s
own direct os.environ.get("ENABLED_BRANDS", ...) rather than routing through
config.py's get_enabled_ser_providers() (that helper serves a different
caller: app.py's startup wiring).

Also validates that ENCRYPTION_KEY and ELPARKING_API_BASE_URL are present
when elparking is enabled, failing fast at build_providers() time rather than
deferring to the first connection attempt.
"""

import logging
import os

from mobility_manager.domain.ports.city_repository import CityRepository
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.ports.ser_zone_repository import SerZoneRepository
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
    PostgresElParkingZoneMappingRepository,
)

logger = logging.getLogger(__name__)

_ELPARKING_CODE = "elparking"


class SerTicketProviderRegistry:
    """Returns the mapping of currently available SerTicketProviderPort implementations."""

    def build_providers(
        self,
        ser_zone_repo: SerZoneRepository,
        city_repo: CityRepository,
        zone_mapping_repo: PostgresElParkingZoneMappingRepository,
    ) -> dict[str, SerTicketProviderPort]:
        """
        Instantiate every enabled SER ticket provider, keyed by provider name.

        Args:
            ser_zone_repo: Threaded into ElParkingSerTicketProvider for
                spatial containment lookups (our own zone geometry).
            city_repo: Threaded into ElParkingSerTicketProvider to resolve
                city names for ElParking town matching.
            zone_mapping_repo: Threaded into ElParkingSerTicketProvider as
                its ElParking town/zone/rate ID-translation cache.

        Returns an empty dict when no known provider is enabled — callers
        must treat this as an expected, handleable condition rather than an
        error (mirrors BrandRegistry).

        Raises:
            RuntimeError: If "elparking" is enabled but ENCRYPTION_KEY or
                ELPARKING_API_BASE_URL is not set.
        """
        raw = os.environ.get("ENABLED_SER_PROVIDERS", "elparking")
        codes = [c.strip().lower() for c in raw.split(",") if c.strip()]

        providers: dict[str, SerTicketProviderPort] = {}
        for code in codes:
            if code == _ELPARKING_CODE:
                # Validate required config is present before instantiating the provider
                if not os.environ.get("ENCRYPTION_KEY"):
                    raise RuntimeError(
                        "ENCRYPTION_KEY must be set when the elparking SER ticket provider is enabled. "
                        'Generate one with: python -c "from cryptography.fernet import Fernet; '
                        'print(Fernet.generate_key().decode())"'
                    )
                if not os.environ.get("ELPARKING_API_BASE_URL"):
                    raise RuntimeError(
                        "ELPARKING_API_BASE_URL must be set when the elparking SER ticket provider is enabled."
                    )

                from mobility_manager.infrastructure.ser_ticket_providers.elparking.provider import (
                    ElParkingSerTicketProvider,
                )

                providers[_ELPARKING_CODE] = ElParkingSerTicketProvider(
                    ser_zone_repo=ser_zone_repo,
                    city_repo=city_repo,
                    zone_mapping_repo=zone_mapping_repo,
                )
                logger.info("ElParking SER ticket provider registered")

            else:
                logger.warning("ENABLED_SER_PROVIDERS contains unknown provider %r — skipping", code)

        return providers
