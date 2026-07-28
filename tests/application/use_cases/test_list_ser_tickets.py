"""
Unit tests for ListSerTickets use case.

Note: ownership is not checked at this layer — see the router's
`require_owned_vehicle` dependency (mirrors ListVehicleLocationHistory, which
is also a thin wrapper with no ownership logic of its own).
"""

from datetime import UTC, datetime
from uuid import uuid4

from mobility_manager.application.use_cases.list_ser_tickets import ListSerTickets
from mobility_manager.domain.entities.parking_ticket import ParkingTicket


class InMemoryParkingTicketRepo:
    def __init__(self, tickets: list[ParkingTicket] | None = None) -> None:
        self._tickets = tickets or []
        self.last_call: tuple[object, ...] | None = None

    def list_by_vehicle(self, vehicle_id, limit, offset) -> tuple[list[ParkingTicket], bool]:
        self.last_call = (vehicle_id, limit, offset)
        page = self._tickets[offset : offset + limit]
        has_more = offset + limit < len(self._tickets)
        return page, has_more


def _make_ticket(vehicle_id=None) -> ParkingTicket:
    if vehicle_id is None:
        vehicle_id = uuid4()
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=uuid4(),
        provider="elparking",
        duration_minutes=60,
        provider_reference="REF-001",
        cost=1.2,
        end_date=datetime.now(UTC),
        created_at=datetime.now(UTC),
        city_code="madrid",
        zone_number="163",
        latitude=40.4,
        longitude=-3.7,
        auto_created=True,
    )


def test_returns_page_and_has_more_from_repo() -> None:
    vehicle_id = uuid4()
    tickets = [_make_ticket(vehicle_id) for _ in range(3)]
    repo = InMemoryParkingTicketRepo(tickets=tickets)
    uc = ListSerTickets(ticket_repo=repo)

    items, has_more = uc.execute(vehicle_id, limit=5, offset=0)

    assert items == tickets
    assert has_more is False


def test_delegates_vehicle_id_limit_and_offset_to_repo() -> None:
    vehicle_id = uuid4()
    repo = InMemoryParkingTicketRepo(tickets=[])
    uc = ListSerTickets(ticket_repo=repo)

    uc.execute(vehicle_id, limit=5, offset=10)

    assert repo.last_call == (vehicle_id, 5, 10)


def test_vehicle_with_no_tickets_returns_empty_page() -> None:
    repo = InMemoryParkingTicketRepo(tickets=[])
    uc = ListSerTickets(ticket_repo=repo)

    items, has_more = uc.execute(uuid4(), limit=5, offset=0)

    assert items == []
    assert has_more is False
