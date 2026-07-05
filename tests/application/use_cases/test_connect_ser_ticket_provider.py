"""
Unit tests for ConnectSerTicketProvider use case.
"""

from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.connect_ser_ticket_provider import (
    ConnectSerTicketProvider,
)
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import SerTicketProviderNotFoundError
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)


class FakeSerTicketProvider(SerTicketProviderPort):
    def __init__(self) -> None:
        self.login_calls: list[SerProviderCredentials] = []

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        self.login_calls.append(credentials)
        return SerProviderSession(data={"token": "fake-session-token"})

    def create_ticket(self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int) -> ParkingTicket:
        raise NotImplementedError("Not exercised by ConnectSerTicketProvider tests")

    def logout(self, session: SerProviderSession) -> None:
        raise NotImplementedError("Not exercised by ConnectSerTicketProvider tests")


class InMemoryUserSerProviderConfigRepo:
    def __init__(self) -> None:
        self.saved: dict[tuple[UUID, str], SerProviderSession] = {}

    def save(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        self.saved[(user_id, provider)] = session

    def find(self, user_id: UUID, provider: str) -> SerProviderSession | None:
        return self.saved.get((user_id, provider))


def test_successful_connection_persists_session() -> None:
    provider = FakeSerTicketProvider()
    config_repo = InMemoryUserSerProviderConfigRepo()
    uc = ConnectSerTicketProvider(providers={"madrid_ser_app": provider}, config_repo=config_repo)

    user_id = uuid4()
    credentials = SerProviderCredentials(data={"username": "alice", "password": "s3cr3t"})

    uc.execute(user_id=user_id, provider="madrid_ser_app", credentials=credentials)

    assert provider.login_calls == [credentials]
    stored = config_repo.find(user_id, "madrid_ser_app")
    assert stored is not None
    assert stored.data == {"token": "fake-session-token"}


def test_unknown_provider_raises_without_calling_anything() -> None:
    config_repo = InMemoryUserSerProviderConfigRepo()
    uc = ConnectSerTicketProvider(providers={}, config_repo=config_repo)

    with pytest.raises(SerTicketProviderNotFoundError):
        uc.execute(
            user_id=uuid4(),
            provider="unknown_provider",
            credentials=SerProviderCredentials(data={}),
        )

    assert config_repo.saved == {}
