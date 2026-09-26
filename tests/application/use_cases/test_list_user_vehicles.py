"""
Unit tests for ListUserVehicles use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from mobility_manager.application.use_cases.list_user_vehicles import (
    ListUserVehicles,
    VehicleWithLocation,
)
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.entities.vehicle_share import VehicleShare
from mobility_manager.domain.value_objects.brand import Brand

_USER_A = uuid4()
_USER_B = uuid4()


def _make_vehicle(user_id: UUID, brand: Brand = Brand.GENERIC) -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=brand,
        display_name="Test Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        owner_id=user_id,
    )


def _make_location(vehicle_id: UUID) -> VehicleLocation:
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=40.4168,
        longitude=-3.7038,
        recorded_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source="push",  # type: ignore[arg-type]
    )


class InMemoryVehicleRepo:
    def __init__(self) -> None:
        self.vehicles: list[Vehicle] = []

    def save(self, vehicle: Vehicle) -> None:
        self.vehicles.append(vehicle)

    def get_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return next((v for v in self.vehicles if v.id == vehicle_id), None)

    def find_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self.get_by_id(vehicle_id)

    def get_all_by_brand(self, brand: Brand) -> list[Vehicle]:
        return [v for v in self.vehicles if v.brand == brand]

    def get_all_by_owner_id(self, user_id: UUID) -> list[Vehicle]:
        return [v for v in self.vehicles if v.owner_id == user_id]

    def delete(self, vehicle_id: UUID) -> None:
        self.vehicles = [v for v in self.vehicles if v.id != vehicle_id]

    def update_display_name(self, vehicle_id: UUID, display_name: str) -> None:
        for v in self.vehicles:
            if v.id == vehicle_id:
                object.__setattr__(v, "display_name", display_name)

    def update_license_plate(self, vehicle_id: UUID, license_plate: str | None) -> None:
        pass


class InMemoryLocationRepo:
    def __init__(self) -> None:
        self.locations: dict[UUID, VehicleLocation] = {}

    def save(self, location: VehicleLocation) -> None:
        self.locations[location.vehicle_id] = location

    def get_latest(self, vehicle_id: UUID) -> VehicleLocation | None:
        return self.locations.get(vehicle_id)


class InMemoryParkingTicketRepo:
    def __init__(self) -> None:
        self.vehicle_ids_with_tickets: set[UUID] = set()

    def has_any_for_vehicle(self, vehicle_id: UUID) -> bool:
        return vehicle_id in self.vehicle_ids_with_tickets


class InMemoryVehicleShareRepo:
    def __init__(self) -> None:
        self.shares: list[VehicleShare] = []

    def save(self, share: VehicleShare) -> None:
        self.shares.append(share)

    def find_by_vehicle_and_user(self, vehicle_id: UUID, user_id: UUID) -> VehicleShare | None:
        return next(
            (s for s in self.shares if s.vehicle_id == vehicle_id and s.user_id == user_id),
            None,
        )

    def list_sharees(self, vehicle_id: UUID) -> list[VehicleShare]:
        return [s for s in self.shares if s.vehicle_id == vehicle_id]

    def delete(self, vehicle_id: UUID, user_id: UUID) -> None:
        self.shares = [s for s in self.shares if not (s.vehicle_id == vehicle_id and s.user_id == user_id)]

    def list_vehicle_ids_for_user(self, user_id: UUID) -> list[UUID]:
        return [s.vehicle_id for s in self.shares if s.user_id == user_id]


def _make_use_case() -> tuple[
    ListUserVehicles,
    InMemoryVehicleRepo,
    InMemoryLocationRepo,
    InMemoryParkingTicketRepo,
    InMemoryVehicleShareRepo,
]:
    v_repo = InMemoryVehicleRepo()
    l_repo = InMemoryLocationRepo()
    t_repo = InMemoryParkingTicketRepo()
    s_repo = InMemoryVehicleShareRepo()
    uc = ListUserVehicles(
        vehicle_repo=v_repo,
        location_repo=l_repo,
        ticket_repo=t_repo,
        share_repo=s_repo,
    )
    return uc, v_repo, l_repo, t_repo, s_repo


class TestListUserVehicles:
    def test_empty_list_when_no_vehicles(self) -> None:
        uc, _, _, _, _ = _make_use_case()
        result = uc.execute(_USER_A)
        assert result == []

    def test_returns_vehicles_for_user(self) -> None:
        uc, v_repo, _, _, _ = _make_use_case()
        v1 = _make_vehicle(_USER_A)
        v2 = _make_vehicle(_USER_A)
        v_repo.save(v1)
        v_repo.save(v2)

        result = uc.execute(_USER_A)
        assert len(result) == 2
        assert all(isinstance(r, VehicleWithLocation) for r in result)

    def test_vehicle_without_location_has_none(self) -> None:
        uc, v_repo, _, _, _ = _make_use_case()
        v = _make_vehicle(_USER_A)
        v_repo.save(v)

        result = uc.execute(_USER_A)
        assert len(result) == 1
        assert result[0].vehicle == v
        assert result[0].location is None

    def test_vehicle_with_location_populated(self) -> None:
        uc, v_repo, l_repo, _, _ = _make_use_case()
        v = _make_vehicle(_USER_A)
        v_repo.save(v)
        loc = _make_location(v.id)
        l_repo.save(loc)

        result = uc.execute(_USER_A)
        assert result[0].location == loc

    def test_user_isolation(self) -> None:
        uc, v_repo, _, _, _ = _make_use_case()
        v_a = _make_vehicle(_USER_A)
        v_b = _make_vehicle(_USER_B)
        v_repo.save(v_a)
        v_repo.save(v_b)

        result_a = uc.execute(_USER_A)
        assert len(result_a) == 1
        assert result_a[0].vehicle.owner_id == _USER_A

        result_b = uc.execute(_USER_B)
        assert len(result_b) == 1
        assert result_b[0].vehicle.owner_id == _USER_B

    def test_vehicle_with_auto_created_ticket_has_ser_tickets_true(self) -> None:
        uc, v_repo, _, t_repo, _ = _make_use_case()
        v = _make_vehicle(_USER_A)
        v_repo.save(v)
        t_repo.vehicle_ids_with_tickets.add(v.id)

        result = uc.execute(_USER_A)
        assert result[0].has_ser_tickets is True

    def test_vehicle_with_no_tickets_has_ser_tickets_false(self) -> None:
        uc, v_repo, _, _, _ = _make_use_case()
        v = _make_vehicle(_USER_A)
        v_repo.save(v)

        result = uc.execute(_USER_A)
        assert result[0].has_ser_tickets is False

    def test_includes_shared_vehicles_with_is_owner_false(self) -> None:
        uc, v_repo, _, _, s_repo = _make_use_case()
        owned = _make_vehicle(_USER_A)
        shared = _make_vehicle(_USER_B)
        v_repo.save(owned)
        v_repo.save(shared)
        s_repo.save(VehicleShare(vehicle_id=shared.id, user_id=_USER_A, created_at=datetime.now(UTC)))

        result = uc.execute(_USER_A)

        assert len(result) == 2
        by_id = {r.vehicle.id: r for r in result}
        assert by_id[owned.id].is_owner is True
        assert by_id[shared.id].is_owner is False

    def test_shared_vehicle_skipped_when_also_owned(self) -> None:
        uc, v_repo, _, _, s_repo = _make_use_case()
        vehicle = _make_vehicle(_USER_A)
        v_repo.save(vehicle)
        s_repo.save(VehicleShare(vehicle_id=vehicle.id, user_id=_USER_A, created_at=datetime.now(UTC)))

        result = uc.execute(_USER_A)

        assert len(result) == 1
        assert result[0].is_owner is True

    def test_shared_vehicle_omitted_when_vehicle_not_found(self) -> None:
        uc, v_repo, _, _, s_repo = _make_use_case()
        vehicle = _make_vehicle(_USER_B)
        v_repo.save(vehicle)
        s_repo.save(VehicleShare(vehicle_id=uuid4(), user_id=_USER_A, created_at=datetime.now(UTC)))

        result = uc.execute(_USER_A)

        assert result == []
