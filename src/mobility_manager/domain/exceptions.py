"""
Domain exceptions for the mobility manager.
"""


class SerZoneNotFoundError(Exception):
    """Raised when no SER zone is found for a given location."""

    pass


class VehicleNotFoundError(Exception):
    """Raised when no vehicle is found for a given ID."""

    pass


class VehicleConfigNotFoundError(Exception):
    """Raised when no vehicle configuration is found for a given vehicle ID."""

    pass


class VehicleLocationNotFoundError(Exception):
    """Raised when no location history exists for a given vehicle."""

    pass


class VinNotFoundInAccountError(Exception):
    """Raised when the configured VIN is not found in the Toyota account."""

    pass


class BrandNotEnabledError(Exception):
    """Raised when a vehicle brand is not in the ENABLED_BRANDS list."""

    pass
