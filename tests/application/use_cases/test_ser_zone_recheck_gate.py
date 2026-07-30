"""
Unit tests for SerZoneRecheckGate.

Covers every scenario in the ser-zone-recheck-gate spec: no active ticket
always triggers a recheck (unchanged location, unchanged zone), an active
ticket held gates the movement floor and zone-unchanged skip, a first-ever
recorded location always triggers a recheck regardless of active ticket, and
each caller's own movement floor is used independently (mocked ports, no
real DB). Also covers the specific `logger.info` reason logged at each skip
point (post-implementation fix: restores the granularity the inline handler
code logged before this gate was extracted — see test_create_ser_ticket.py
for this codebase's existing caplog convention).
"""

import logging
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest
from shapely.geometry import Polygon

from mobility_manager.application.use_cases.ser_zone_recheck_gate import (
    SerZoneRecheckGate,
)
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.events.vehicle_location_updated import (
    VehicleLocationUpdated,
)
from mobility_manager.domain.value_objects.location import GeoLocation

_FAR_LAT, _FAR_LNG = 40.4168, -3.7038
_MOVED_LAT, _MOVED_LNG = 40.4258, -3.7038  # ~999m north of _FAR_*, well past any floor used here
_NEAR_LAT, _NEAR_LNG = 40.41681, -3.7038  # ~1.1m from _FAR_*, under any floor >= 5m used here

_SQUARE = Polygon([(440584, 4474459), (440604, 4474459), (440604, 4474479), (440584, 4474479)])


class FakeVehicleLocationRepo:
    def __init__(self) -> None:
        self.previous: VehicleLocation | None = None
        self.get_previous_calls: list[UUID] = []

    def get_previous(self, vehicle_id: UUID, before: datetime) -> VehicleLocation | None:
        self.get_previous_calls.append(vehicle_id)
        return self.previous


class FakeFindContainingSerZone:
    """
    `zone` is the default answer for every call. `zone_queue` lets a test
    give distinct, ordered answers per call (e.g. "previous zone A, then
    current zone B") when the two lookups must differ.
    """

    def __init__(self) -> None:
        self.zone: SerZone | None = None
        self.zone_queue: list[SerZone | None] = []
        self.calls: list[GeoLocation] = []

    def execute(self, location: GeoLocation) -> SerZone | None:
        self.calls.append(location)
        if self.zone_queue:
            return self.zone_queue.pop(0)
        return self.zone


class FakeParkingTicketRepo:
    def __init__(self) -> None:
        self.active_tickets: list[ParkingTicket] = []
        self.calls: list[tuple[UUID, datetime]] = []

    def find_all_active_for_vehicle(self, vehicle_id: UUID, at: datetime) -> list[ParkingTicket]:
        self.calls.append((vehicle_id, at))
        return self.active_tickets


def _make_ser_zone(zone_number: str = "163") -> SerZone:
    return SerZone(
        city_code="madrid",
        zone_number=zone_number,
        zone_type="Azul",
        district="CENTRO",
        spot_count=15,
        geometry=_SQUARE,
    )


def _make_ticket(vehicle_id: UUID) -> ParkingTicket:
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=uuid4(),
        provider="elparking",
        duration_minutes=60,
        provider_reference="ref-123",
        cost=1.5,
        end_date=datetime(2026, 7, 30, 12, 0, tzinfo=UTC),
        created_at=datetime(2026, 7, 30, 10, 0, tzinfo=UTC),
        city_code="madrid",
        zone_number="163",
    )


def _make_event(vehicle_id: UUID, lat: float, lng: float, now: datetime) -> VehicleLocationUpdated:
    return VehicleLocationUpdated(
        vehicle_id=vehicle_id,
        latitude=lat,
        longitude=lng,
        recorded_at=now,
        received_at=now,
        source="push",
    )


def _make_previous_location(vehicle_id: UUID, lat: float, lng: float, now: datetime) -> VehicleLocation:
    return VehicleLocation(
        id=uuid4(),
        vehicle_id=vehicle_id,
        latitude=lat,
        longitude=lng,
        recorded_at=now,
        received_at=now,
        source="push",
    )


class _Fixture:
    def __init__(self) -> None:
        self.location_repo = FakeVehicleLocationRepo()
        self.find_containing = FakeFindContainingSerZone()
        self.ticket_repo = FakeParkingTicketRepo()

    def build(self) -> SerZoneRecheckGate:
        return SerZoneRecheckGate(
            vehicle_location_repo=self.location_repo,  # type: ignore[arg-type]
            find_containing_ser_zone=self.find_containing,  # type: ignore[arg-type]
            ticket_repo=self.ticket_repo,  # type: ignore[arg-type]
        )


def test_no_active_ticket_triggers_recheck_regardless_of_unchanged_movement() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    fx.find_containing.zone = _make_ser_zone(zone_number="163")
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _FAR_LAT, _FAR_LNG, now), movement_floor_meters=10.0)

    assert decision.should_check is True
    assert decision.zone == _make_ser_zone(zone_number="163")


def test_no_active_ticket_triggers_recheck_even_in_unchanged_zone() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    fx.find_containing.zone = _make_ser_zone(zone_number="163")  # same zone for both hypothetical lookups
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=10.0)

    assert decision.should_check is True


def test_active_ticket_movement_below_floor_skips_without_zone_lookup() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _NEAR_LAT, _NEAR_LNG, now), movement_floor_meters=5.0)

    assert decision.should_check is False
    assert decision.zone is None
    assert fx.find_containing.calls == []


def test_active_ticket_movement_past_floor_but_unchanged_zone_skips() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    fx.find_containing.zone = _make_ser_zone(zone_number="163")  # same zone for both lookups
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=5.0)

    assert decision.should_check is False
    assert len(fx.find_containing.calls) == 2


def test_active_ticket_genuine_zone_change_triggers_recheck() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    fx.find_containing.zone_queue = [_make_ser_zone(zone_number="163"), _make_ser_zone(zone_number="200")]
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=5.0)

    assert decision.should_check is True
    assert decision.zone == _make_ser_zone(zone_number="200")


def test_active_ticket_transition_from_outside_all_zones_triggers_recheck() -> None:
    """
    Previous location was outside any SER zone (`(None, None)`), current
    location is inside one — a genuine zone change where the *previous*
    resolved zone is `None`, exercising `_zone_key`'s `None` branch on the
    previous side.
    """
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    fx.find_containing.zone_queue = [None, _make_ser_zone(zone_number="200")]
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=5.0)

    assert decision.should_check is True
    assert decision.zone == _make_ser_zone(zone_number="200")


def test_first_ever_recorded_location_always_triggers_recheck_with_active_ticket() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = None
    fx.find_containing.zone = _make_ser_zone(zone_number="163")
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=10.0)

    assert decision.should_check is True
    assert decision.zone == _make_ser_zone(zone_number="163")


def test_first_ever_recorded_location_always_triggers_recheck_without_active_ticket() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.location_repo.previous = None
    fx.find_containing.zone = None
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=10.0)

    assert decision.should_check is True


def test_each_callers_own_floor_used_independently() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    # Below the 5m floor, the gate never reaches the zone lookup at all, so
    # this queue is only ever consumed by the second (above-floor) call.
    fx.find_containing.zone_queue = [_make_ser_zone(zone_number="163"), _make_ser_zone(zone_number="200")]
    gate = fx.build()
    event = _make_event(vehicle_id, _NEAR_LAT, _NEAR_LNG, now)  # ~1.1m from previous

    below_floor_decision = gate.evaluate(event, movement_floor_meters=5.0)
    above_floor_decision = gate.evaluate(event, movement_floor_meters=0.5)

    assert below_floor_decision.should_check is False
    assert above_floor_decision.should_check is True


def test_ticket_repo_queried_with_event_vehicle_id_and_received_at() -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    gate = fx.build()

    gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=10.0)

    assert fx.ticket_repo.calls == [(vehicle_id, now)]


def test_no_active_ticket_never_calls_get_previous_or_resolves_zone_twice() -> None:
    """
    Spec-mandated ordering: the active-ticket check happens strictly before
    the previous-location fetch, so the "no active ticket" branch
    short-circuits before ever touching location history — it must never
    call `get_previous`, and must resolve the zone exactly once (for the
    event's own coordinates, not a second time for a previous-location
    comparison).
    """
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.find_containing.zone = _make_ser_zone(zone_number="163")
    gate = fx.build()

    decision = gate.evaluate(_make_event(vehicle_id, _FAR_LAT, _FAR_LNG, now), movement_floor_meters=10.0)

    assert decision.should_check is True
    assert fx.location_repo.get_previous_calls == []
    assert fx.find_containing.calls == [GeoLocation(lat=_FAR_LAT, lng=_FAR_LNG)]


def test_movement_below_floor_logs_specific_reason(caplog: pytest.LogCaptureFixture) -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    gate = fx.build()

    with caplog.at_level(logging.INFO):
        decision = gate.evaluate(_make_event(vehicle_id, _NEAR_LAT, _NEAR_LNG, now), movement_floor_meters=5.0)

    assert decision.should_check is False
    assert any(
        "GPS-noise floor" in record.message and str(vehicle_id) in record.message for record in caplog.records
    )


def test_zone_unchanged_logs_specific_reason(caplog: pytest.LogCaptureFixture) -> None:
    vehicle_id, now = uuid4(), datetime.now(UTC)
    fx = _Fixture()
    fx.ticket_repo.active_tickets = [_make_ticket(vehicle_id)]
    fx.location_repo.previous = _make_previous_location(vehicle_id, _FAR_LAT, _FAR_LNG, now)
    fx.find_containing.zone = _make_ser_zone(zone_number="163")  # same zone for both lookups
    gate = fx.build()

    with caplog.at_level(logging.INFO):
        decision = gate.evaluate(_make_event(vehicle_id, _MOVED_LAT, _MOVED_LNG, now), movement_floor_meters=5.0)

    assert decision.should_check is False
    assert any(
        "SER zone unchanged" in record.message and str(vehicle_id) in record.message for record in caplog.records
    )
