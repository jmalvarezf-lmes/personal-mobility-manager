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


class SerTicketProviderNotFoundError(Exception):
    """Raised when a requested SER ticket provider name is not registered."""

    pass


class SerProviderSessionNotFoundError(Exception):
    """Raised when no stored session exists for a given (user_id, provider) pair."""

    pass


class SerProviderAuthenticationError(Exception):
    """Raised when a SER ticket provider rejects login credentials as invalid."""

    pass


class SerProviderApiError(Exception):
    """Raised for non-authentication SER ticket provider failures (network, rate limit, 5xx, malformed)."""

    pass
