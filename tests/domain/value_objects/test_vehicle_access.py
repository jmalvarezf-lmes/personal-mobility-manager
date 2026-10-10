"""
Unit tests for the VehicleAccess value object.
"""

from datetime import UTC, datetime
from uuid import uuid4

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.vehicle_access import VehicleAccess


def _make_vehicle():
    return Vehicle(
        id=uuid4(),
        brand=Brand.GENERIC,
        display_name="Test Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        owner_id=uuid4(),
    )


def test_vehicle_access_equality() -> None:
    vehicle = _make_vehicle()

    access_a = VehicleAccess(vehicle=vehicle, is_owner=True)
    access_b = VehicleAccess(vehicle=vehicle, is_owner=True)

    assert access_a == access_b


def test_vehicle_access_distinguishes_owner_and_sharee() -> None:
    vehicle = _make_vehicle()

    owner_access = VehicleAccess(vehicle=vehicle, is_owner=True)
    sharee_access = VehicleAccess(vehicle=vehicle, is_owner=False)

    assert owner_access != sharee_access
