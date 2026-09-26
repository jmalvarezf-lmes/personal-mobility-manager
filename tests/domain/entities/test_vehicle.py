"""
Unit tests for the Vehicle domain entity.
"""

from datetime import UTC, datetime
from uuid import uuid4

from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.value_objects.brand import Brand


def _make_vehicle(owner_id=None):
    return Vehicle(
        id=uuid4(),
        brand=Brand.GENERIC,
        display_name="Test Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        owner_id=owner_id or uuid4(),
    )


def test_is_owned_by_returns_true_for_owner() -> None:
    owner_id = uuid4()
    vehicle = _make_vehicle(owner_id)

    assert vehicle.is_owned_by(owner_id) is True


def test_is_owned_by_returns_false_for_non_owner() -> None:
    vehicle = _make_vehicle(uuid4())
    other_user_id = uuid4()

    assert vehicle.is_owned_by(other_user_id) is False
