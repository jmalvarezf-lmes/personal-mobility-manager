"""
Unit tests for CreateSerTicket use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.create_ser_ticket import CreateSerTicket
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import (
    SerProviderSessionNotFoundError,
    SerTicketProviderNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)

_OWNER = uuid4()
_OTHER_USER = uuid4()


def _make_vehicle(user_id: UUID) -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=Brand.GENERIC,
        display_name="Test Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        user_id=user_id,
    )


class FakeSerTicketProvider(SerTicketProviderPort):
    def __init__(self) -> None:
        self.create_ticket_calls: list[tuple[SerProviderSession, Vehicle, int]] = []

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        raise NotImplementedError("Not exercised by CreateSerTicket tests")

    def create_ticket(self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int) -> ParkingTicket:
        self.create_ticket_calls.append((session, vehicle, duration_minutes))
        return ParkingTicket(
            id=uuid4(),
            vehicle_id=vehicle.id,
            user_id=vehicle.user_id,
            provider="madrid_ser_app",
            duration_minutes=duration_minutes,
            provider_reference="REF-123",
            created_at=datetime.now(UTC),
        )


class InMemoryVehicleRepo:
    def __init__(self) -> None:
        self.vehicles: dict[UUID, Vehicle] = {}

    def add(self, vehicle: Vehicle) -> None:
        self.vehicles[vehicle.id] = vehicle

    def find_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self.vehicles.get(vehicle_id)


class InMemoryUserSerProviderConfigRepo:
    def __init__(self) -> None:
        self.sessions: dict[tuple[UUID, str], SerProviderSession] = {}

    def add(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        self.sessions[(user_id, provider)] = session

    def find(self, user_id: UUID, provider: str) -> SerProviderSession | None:
        return self.sessions.get((user_id, provider))

    def save(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        self.sessions[(user_id, provider)] = session


class InMemoryParkingTicketRepo:
    def __init__(self) -> None:
        self.saved: list[ParkingTicket] = []

    def save(self, ticket: ParkingTicket) -> None:
        self.saved.append(ticket)


def _make_use_case():
    vehicle_repo = InMemoryVehicleRepo()
    config_repo = InMemoryUserSerProviderConfigRepo()
    ticket_repo = InMemoryParkingTicketRepo()
    provider = FakeSerTicketProvider()
    uc = CreateSerTicket(
        vehicle_repo=vehicle_repo,
        config_repo=config_repo,
        ticket_repo=ticket_repo,
        providers={"madrid_ser_app": provider},
    )
    return uc, vehicle_repo, config_repo, ticket_repo, provider


def test_successful_ticket_creation_persists_and_returns_ticket() -> None:
    uc, vehicle_repo, config_repo, ticket_repo, provider = _make_use_case()
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    session = SerProviderSession(data={"token": "abc"})
    config_repo.add(_OWNER, "madrid_ser_app", session)

    result = uc.execute(user_id=_OWNER, vehicle_id=vehicle.id, provider="madrid_ser_app", duration_minutes=90)

    assert provider.create_ticket_calls == [(session, vehicle, 90)]
    assert ticket_repo.saved == [result]
    assert result.vehicle_id == vehicle.id
    assert result.duration_minutes == 90


def test_vehicle_not_owned_by_user_raises_vehicle_not_found() -> None:
    uc, vehicle_repo, config_repo, ticket_repo, provider = _make_use_case()
    vehicle = _make_vehicle(_OTHER_USER)
    vehicle_repo.add(vehicle)
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={}))

    with pytest.raises(VehicleNotFoundError):
        uc.execute(user_id=_OWNER, vehicle_id=vehicle.id, provider="madrid_ser_app", duration_minutes=60)

    assert provider.create_ticket_calls == []
    assert ticket_repo.saved == []


def test_unknown_vehicle_raises_vehicle_not_found() -> None:
    uc, _vehicle_repo, config_repo, _ticket_repo, provider = _make_use_case()
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={}))

    with pytest.raises(VehicleNotFoundError):
        uc.execute(user_id=_OWNER, vehicle_id=uuid4(), provider="madrid_ser_app", duration_minutes=60)

    assert provider.create_ticket_calls == []


def test_missing_session_raises_session_not_found() -> None:
    uc, vehicle_repo, _config_repo, _ticket_repo, provider = _make_use_case()
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)

    with pytest.raises(SerProviderSessionNotFoundError):
        uc.execute(user_id=_OWNER, vehicle_id=vehicle.id, provider="madrid_ser_app", duration_minutes=60)

    assert provider.create_ticket_calls == []


def test_unregistered_provider_raises_provider_not_found() -> None:
    vehicle_repo = InMemoryVehicleRepo()
    config_repo = InMemoryUserSerProviderConfigRepo()
    ticket_repo = InMemoryParkingTicketRepo()
    uc = CreateSerTicket(vehicle_repo=vehicle_repo, config_repo=config_repo, ticket_repo=ticket_repo, providers={})

    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={}))

    with pytest.raises(SerTicketProviderNotFoundError):
        uc.execute(user_id=_OWNER, vehicle_id=vehicle.id, provider="madrid_ser_app", duration_minutes=60)

    assert ticket_repo.saved == []
