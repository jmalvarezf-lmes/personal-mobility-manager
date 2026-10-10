"""
Unit tests for the VehicleShare domain entity.
"""

from datetime import UTC, datetime
from uuid import uuid4

from mobility_manager.domain.entities.vehicle_share import VehicleShare


def test_vehicle_share_equality_and_hashability() -> None:
    vehicle_id = uuid4()
    user_id = uuid4()
    created_at = datetime.now(UTC)

    share_a = VehicleShare(vehicle_id=vehicle_id, user_id=user_id, created_at=created_at)
    share_b = VehicleShare(vehicle_id=vehicle_id, user_id=user_id, created_at=created_at)

    assert share_a == share_b
    assert hash(share_a) == hash(share_b)


def test_vehicle_share_inequality_when_fields_differ() -> None:
    created_at = datetime.now(UTC)
    base = VehicleShare(vehicle_id=uuid4(), user_id=uuid4(), created_at=created_at)

    assert base != VehicleShare(vehicle_id=uuid4(), user_id=base.user_id, created_at=created_at)
    assert base != VehicleShare(vehicle_id=base.vehicle_id, user_id=uuid4(), created_at=created_at)
    assert base != VehicleShare(
        vehicle_id=base.vehicle_id, user_id=base.user_id, created_at=datetime(2020, 1, 1, tzinfo=UTC)
    )
