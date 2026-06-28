"""
Port (interface): ParkingServicePort.

Abstract contract that all city parking adapters must implement.
New cities (e.g. Barcelona, Valencia) plug in by implementing this interface.
"""


class ParkingServicePort:
    """Base parking service port — implemented per city in infrastructure."""

    pass
