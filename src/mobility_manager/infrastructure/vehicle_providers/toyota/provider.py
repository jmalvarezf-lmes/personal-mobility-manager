"""
Infrastructure adapter: ToyotaVehicleProvider.

Implements VehicleProviderPort using the pytoyoda library to communicate
with the Toyota MyT API. Add other vendors alongside this directory.
"""
from mobility_manager.domain.ports.vehicle_provider import VehicleProviderPort


class ToyotaVehicleProvider(VehicleProviderPort):
    """Fetches vehicle data from Toyota MyT via pytoyoda."""

    pass
