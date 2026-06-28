"""
Infrastructure: BrandRegistry.

Reads ENABLED_BRANDS env var (comma-separated, default "generic") and returns
one VehiclePullLocationPort instance per pull-capable brand.

Generic brand is push-only and produces no pull provider.
Unknown brand codes are logged as warnings and skipped.

Also validates that ENCRYPTION_KEY is present when Toyota is enabled.
"""
import logging
import os

from mobility_manager.domain.ports.vehicle_pull_location_port import (
    VehiclePullLocationPort,
)
from mobility_manager.domain.value_objects.brand import Brand

logger = logging.getLogger(__name__)


class BrandRegistry:
    """Returns the list of active VehiclePullLocationPort instances."""

    def build_pull_providers(self) -> list[VehiclePullLocationPort]:
        """
        Instantiate one pull provider per enabled pull-capable brand.

        Returns an empty list if no pull-capable brands are enabled (e.g. generic-only).

        Raises:
            RuntimeError: If Toyota is enabled but ENCRYPTION_KEY is not set.
        """
        raw = os.environ.get("ENABLED_BRANDS", "generic")
        codes = [c.strip().lower() for c in raw.split(",") if c.strip()]

        providers: list[VehiclePullLocationPort] = []
        for code in codes:
            if code == Brand.TOYOTA.value:
                # Validate encryption key is present before instantiating Toyota provider
                if not os.environ.get("ENCRYPTION_KEY"):
                    raise RuntimeError(
                        "ENCRYPTION_KEY must be set when Toyota brand is enabled. "
                        "Generate one with: python -c \"from cryptography.fernet import Fernet; "
                        "print(Fernet.generate_key().decode())\""
                    )
                from mobility_manager.infrastructure.vehicle_providers.toyota.location_provider import (
                    ToyotaLocationProvider,
                )

                providers.append(ToyotaLocationProvider())
                logger.info("Toyota pull provider registered")

            elif code == Brand.GENERIC.value:
                # Generic is push-only — no pull provider
                logger.debug("Generic brand is push-only; no pull provider added")

            else:
                logger.warning(
                    "ENABLED_BRANDS contains unknown brand %r — skipping", code
                )

        return providers
