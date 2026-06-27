"""
Port (interface): ParkingServicePort.

Abstract contract that all city parking adapters must implement.
New cities (e.g. Barcelona, Valencia) plug in by implementing this interface.
"""
from abc import ABC


class ParkingServicePort(ABC):
    """Abstract parking service — implemented per city in infrastructure."""

    pass
