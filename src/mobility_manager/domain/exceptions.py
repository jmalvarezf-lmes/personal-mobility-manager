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


class NotificationChannelApiError(Exception):
    """Raised when a notification channel's API call fails (network error, unexpected status)."""

    pass


class InvalidNotificationConfigError(Exception):
    """Raised when a notification type's `config` dict fails validation against its `config_schema`."""

    pass


class InvalidSerParkingExemptionZoneError(Exception):
    """Raised when a (city_code, zone_number) pair has no matching ser_zone_areas row."""

    pass


class SerProviderVehicleNotFoundError(Exception):
    """Raised when a vehicle's license plate cannot be matched against a SER ticket provider's own vehicle records."""

    pass


class SerTicketPersistenceError(Exception):
    """
    Raised when a SER ticket provider has already created (and charged) a
    real ticket, but persisting our own ParkingTicket record afterwards
    fails.

    Distinguishes this specific "charged but unpersisted" case from an
    ordinary creation failure — see CreateSerTicket.execute(), whose ticket
    repository save() failure is re-raised as this type instead of a bare
    `raise`, and SerTicketCreationTriggerHandler's exception-to-reason
    mapping, which maps it to the closed-vocabulary reason
    `"ticket_created_but_not_recorded"` (never leaked verbatim into any
    user-facing notification).
    """

    pass
