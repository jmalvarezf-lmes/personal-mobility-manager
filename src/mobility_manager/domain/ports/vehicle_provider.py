"""
Port (interface): VehicleProviderPort.

Abstract contract that all vehicle vendor adapters must implement.
New vendors (e.g. Volkswagen, BMW) plug in by implementing this interface.
"""
from abc import ABC


class VehicleProviderPort(ABC):
    """Abstract vehicle provider — implemented per vendor in infrastructure."""

    pass
