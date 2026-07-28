"""
Integration tests for PostgresParkingTicketRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent.
"""

import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text

from mobility_manager.domain.entities.parking_ticket import ParkingTicket


@pytest.fixture()
def pg_engine():
    dsn = os.environ.get("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN not set — skipping integration test")
    engine = create_engine(dsn, pool_pre_ping=True)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id UUID PRIMARY KEY,
                    google_sub TEXT NOT NULL UNIQUE,
                    email TEXT NOT NULL,
                    display_name TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS vehicles (
                    id UUID PRIMARY KEY,
                    brand VARCHAR(20) NOT NULL,
                    display_name VARCHAR(255) NOT NULL,
                    vin VARCHAR(50),
                    created_at TIMESTAMPTZ NOT NULL,
                    user_id UUID NOT NULL REFERENCES users(id)
                )
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE TABLE IF NOT EXISTS parking_tickets (
                    id UUID PRIMARY KEY,
                    vehicle_id UUID NOT NULL REFERENCES vehicles(id),
                    user_id UUID NOT NULL REFERENCES users(id),
                    provider TEXT NOT NULL,
                    duration_minutes INT NOT NULL,
                    provider_reference TEXT,
                    cost NUMERIC NOT NULL,
                    end_date TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    city_code TEXT,
                    zone_number TEXT,
                    latitude DOUBLE PRECISION,
                    longitude DOUBLE PRECISION,
                    auto_created BOOLEAN
                )
                """
            )
        )
        conn.execute(text("TRUNCATE parking_tickets, vehicles, users CASCADE"))
    yield engine
    with engine.begin() as conn:
        conn.execute(text("TRUNCATE parking_tickets, vehicles, users CASCADE"))
    engine.dispose()


def _insert_user_and_vehicle(engine, user_id, vehicle_id) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO users (id, google_sub, email, display_name, created_at)"
                " VALUES (:id, :sub, 'test@example.com', 'Test User', :now)"
            ),
            {"id": str(user_id), "sub": str(uuid4()), "now": datetime.now(UTC)},
        )
        conn.execute(
            text(
                "INSERT INTO vehicles (id, brand, display_name, created_at, user_id)"
                " VALUES (:id, 'generic', 'Test', :now, :user_id)"
            ),
            {"id": str(vehicle_id), "now": datetime.now(UTC), "user_id": str(user_id)},
        )


def test_save_persists_all_fields(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    user_id = uuid4()
    vehicle_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)

    ticket_id = uuid4()
    created_at = datetime.now(UTC)
    end_date = datetime.now(UTC)
    ticket = ParkingTicket(
        id=ticket_id,
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="madrid_ser_app",
        duration_minutes=120,
        provider_reference="REF-001",
        cost=1.2,
        end_date=end_date,
        created_at=created_at,
        city_code="madrid",
        zone_number="163",
        latitude=40.4,
        longitude=-3.7,
        auto_created=True,
    )
    repo.save(ticket)

    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT * FROM parking_tickets WHERE id = :id"),
            {"id": str(ticket_id)},
        ).fetchone()

    assert row is not None
    assert row.vehicle_id == vehicle_id
    assert row.user_id == user_id
    assert row.provider == "madrid_ser_app"
    assert row.duration_minutes == 120
    assert row.provider_reference == "REF-001"
    assert float(row.cost) == 1.2
    assert row.end_date == end_date
    assert row.city_code == "madrid"
    assert row.zone_number == "163"
    assert row.latitude == pytest.approx(40.4)
    assert row.longitude == pytest.approx(-3.7)
    assert row.auto_created is True


def test_save_with_none_provider_reference(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    user_id = uuid4()
    vehicle_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)

    ticket_id = uuid4()
    ticket = ParkingTicket(
        id=ticket_id,
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="madrid_ser_app",
        duration_minutes=60,
        provider_reference=None,
        cost=0.6,
        end_date=datetime.now(UTC),
        created_at=datetime.now(UTC),
        city_code="madrid",
        zone_number="163",
    )
    repo.save(ticket)

    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT provider_reference FROM parking_tickets WHERE id = :id"),
            {"id": str(ticket_id)},
        ).fetchone()

    assert row is not None
    assert row.provider_reference is None


def test_save_with_none_zone_fields_round_trips_as_none_legacy_row(pg_engine) -> None:
    """
    Simulates a legacy pre-migration row: city_code/zone_number both None.

    Covers the D5 fail-safe's data-layer precondition — the repository must
    round-trip a None zone unchanged, not coerce it to any other value.
    """
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    user_id = uuid4()
    vehicle_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)

    ticket_id = uuid4()
    ticket = ParkingTicket(
        id=ticket_id,
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="madrid_ser_app",
        duration_minutes=60,
        provider_reference="REF-002",
        cost=0.6,
        end_date=datetime.now(UTC),
        created_at=datetime.now(UTC),
        city_code=None,
        zone_number=None,
        latitude=None,
        longitude=None,
        auto_created=None,
    )
    repo.save(ticket)

    found = repo.find_all_active_for_vehicle(vehicle_id, at=datetime.now(UTC) - timedelta(minutes=1))
    assert len(found) == 1
    assert found[0].city_code is None
    assert found[0].zone_number is None
    assert found[0].latitude is None
    assert found[0].longitude is None
    assert found[0].auto_created is None


def _make_ticket(vehicle_id, user_id, end_date: datetime, created_at: datetime | None = None) -> ParkingTicket:
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="elparking",
        duration_minutes=60,
        provider_reference="REF-001",
        cost=1.2,
        end_date=end_date,
        created_at=created_at or datetime.now(UTC),
        city_code="madrid",
        zone_number="163",
    )


def test_find_all_active_for_vehicle_returns_empty_list_when_no_tickets(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)

    assert repo.find_all_active_for_vehicle(vehicle_id, at=datetime.now(UTC)) == []


def test_find_all_active_for_vehicle_returns_empty_list_when_only_expired_ticket(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    now = datetime.now(UTC)
    repo.save(_make_ticket(vehicle_id, user_id, end_date=now - timedelta(minutes=5)))

    assert repo.find_all_active_for_vehicle(vehicle_id, at=now) == []


def test_find_all_active_for_vehicle_returns_ticket_still_active(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    now = datetime.now(UTC)
    ticket = _make_ticket(vehicle_id, user_id, end_date=now + timedelta(minutes=30))
    repo.save(ticket)

    found = repo.find_all_active_for_vehicle(vehicle_id, at=now)

    assert len(found) == 1
    assert found[0].id == ticket.id


def test_find_all_active_for_vehicle_returns_all_active_tickets(pg_engine) -> None:
    """
    Task 9.5 (4R review fix #1): two simultaneously-active tickets for the
    same vehicle in different zones must both be returned, not just the one
    with the latest end_date — the corrected list-based contract.
    """
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    now = datetime.now(UTC)
    earlier_zone_a = _make_ticket(vehicle_id, user_id, end_date=now + timedelta(minutes=10))
    repo.save(earlier_zone_a)
    later_zone_b = ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="elparking",
        duration_minutes=60,
        provider_reference="REF-002",
        cost=1.2,
        end_date=now + timedelta(minutes=60),
        created_at=now,
        city_code="madrid",
        zone_number="200",
    )
    repo.save(later_zone_b)

    found = repo.find_all_active_for_vehicle(vehicle_id, at=now)

    assert {t.id for t in found} == {earlier_zone_a.id, later_zone_b.id}


def test_find_all_active_for_vehicle_is_scoped_to_the_given_vehicle(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    other_vehicle_id = uuid4()
    user_id = uuid4()
    other_user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    _insert_user_and_vehicle(pg_engine, other_user_id, other_vehicle_id)
    now = datetime.now(UTC)
    repo.save(_make_ticket(other_vehicle_id, other_user_id, end_date=now + timedelta(minutes=30)))

    assert repo.find_all_active_for_vehicle(vehicle_id, at=now) == []


# ---------------------------------------------------------------------------
# list_by_vehicle (task 4.4)
# ---------------------------------------------------------------------------


def _make_ticket_with_provenance(
    vehicle_id, user_id, created_at: datetime, auto_created: bool | None
) -> ParkingTicket:
    return ParkingTicket(
        id=uuid4(),
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="elparking",
        duration_minutes=60,
        provider_reference="REF-001",
        cost=1.2,
        end_date=created_at + timedelta(hours=1),
        created_at=created_at,
        city_code="madrid",
        zone_number="163",
        latitude=40.4,
        longitude=-3.7,
        auto_created=auto_created,
    )


def test_list_by_vehicle_returns_every_ticket_regardless_of_auto_created(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    now = datetime.now(UTC)
    for i in range(3):
        repo.save(_make_ticket_with_provenance(vehicle_id, user_id, now + timedelta(minutes=i), auto_created=True))
    for i in range(2):
        repo.save(
            _make_ticket_with_provenance(vehicle_id, user_id, now + timedelta(minutes=10 + i), auto_created=False)
        )

    items, has_more = repo.list_by_vehicle(vehicle_id, limit=10, offset=0)

    assert len(items) == 5
    assert has_more is False
    assert {t.auto_created for t in items} == {True, False}


def test_list_by_vehicle_returns_newest_first_page(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    now = datetime.now(UTC)
    tickets = [
        _make_ticket_with_provenance(vehicle_id, user_id, now + timedelta(minutes=i), auto_created=True)
        for i in range(10)
    ]
    for ticket in tickets:
        repo.save(ticket)

    items, has_more = repo.list_by_vehicle(vehicle_id, limit=5, offset=0)

    assert has_more is True
    assert [t.id for t in items] == [t.id for t in reversed(tickets[5:10])]


def test_list_by_vehicle_reports_no_further_pages(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    now = datetime.now(UTC)
    for i in range(3):
        repo.save(_make_ticket_with_provenance(vehicle_id, user_id, now + timedelta(minutes=i), auto_created=True))

    items, has_more = repo.list_by_vehicle(vehicle_id, limit=5, offset=0)

    assert len(items) == 3
    assert has_more is False


def test_list_by_vehicle_out_of_range_offset_returns_empty(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    now = datetime.now(UTC)
    repo.save(_make_ticket_with_provenance(vehicle_id, user_id, now, auto_created=True))

    items, has_more = repo.list_by_vehicle(vehicle_id, limit=5, offset=100)

    assert items == []
    assert has_more is False


def test_list_by_vehicle_paginates_deterministically_with_identical_created_at(pg_engine) -> None:
    """
    Task 14.1: `created_at` DESC alone is not a stable sort key when two
    tickets share the same value — without the secondary `id ASC` tiebreaker,
    consecutive paged queries could return an overlapping or skipped row at
    the page boundary. Paging through with `limit=1` twice must return two
    distinct ticket ids.
    """
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    same_created_at = datetime.now(UTC)
    repo.save(_make_ticket_with_provenance(vehicle_id, user_id, same_created_at, auto_created=True))
    repo.save(_make_ticket_with_provenance(vehicle_id, user_id, same_created_at, auto_created=False))

    page_0, _ = repo.list_by_vehicle(vehicle_id, limit=1, offset=0)
    page_1, _ = repo.list_by_vehicle(vehicle_id, limit=1, offset=1)

    assert len(page_0) == 1
    assert len(page_1) == 1
    assert page_0[0].id != page_1[0].id


# ---------------------------------------------------------------------------
# has_any_for_vehicle (task 6.1)
# ---------------------------------------------------------------------------


def test_has_any_for_vehicle_false_when_no_tickets(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)

    assert repo.has_any_for_vehicle(vehicle_id) is False


def test_has_any_for_vehicle_true_with_only_manual_tickets(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    repo.save(_make_ticket_with_provenance(vehicle_id, user_id, datetime.now(UTC), auto_created=False))

    assert repo.has_any_for_vehicle(vehicle_id) is True


def test_has_any_for_vehicle_true_with_auto_created_ticket(pg_engine) -> None:
    from mobility_manager.infrastructure.repositories.postgres.parking_ticket_repo import (
        PostgresParkingTicketRepository,
    )

    repo = PostgresParkingTicketRepository(pg_engine)
    vehicle_id = uuid4()
    user_id = uuid4()
    _insert_user_and_vehicle(pg_engine, user_id, vehicle_id)
    repo.save(_make_ticket_with_provenance(vehicle_id, user_id, datetime.now(UTC), auto_created=True))

    assert repo.has_any_for_vehicle(vehicle_id) is True
