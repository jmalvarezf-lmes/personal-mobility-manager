"""
Integration tests for PostgresParkingTicketRepository.

Requires POSTGRES_DSN environment variable. Skipped automatically if absent.
"""

import os
from datetime import UTC, datetime
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
                    created_at TIMESTAMPTZ NOT NULL
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
    ticket = ParkingTicket(
        id=ticket_id,
        vehicle_id=vehicle_id,
        user_id=user_id,
        provider="madrid_ser_app",
        duration_minutes=120,
        provider_reference="REF-001",
        created_at=created_at,
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
        created_at=datetime.now(UTC),
    )
    repo.save(ticket)

    with pg_engine.connect() as conn:
        row = conn.execute(
            text("SELECT provider_reference FROM parking_tickets WHERE id = :id"),
            {"id": str(ticket_id)},
        ).fetchone()

    assert row is not None
    assert row.provider_reference is None
