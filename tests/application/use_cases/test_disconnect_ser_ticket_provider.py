"""
Unit tests for DisconnectSerTicketProvider use case.
"""

from uuid import UUID, uuid4

from mobility_manager.application.use_cases.disconnect_ser_ticket_provider import (
    DisconnectSerTicketProvider,
)
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import SerProviderApiError
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)


class FakeSerTicketProvider(SerTicketProviderPort):
    def __init__(self, logout_error: Exception | None = None) -> None:
        self.logout_calls: list[SerProviderSession] = []
        self._logout_error = logout_error

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        raise NotImplementedError("Not exercised by DisconnectSerTicketProvider tests")

    def create_ticket(self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int) -> ParkingTicket:
        raise NotImplementedError("Not exercised by DisconnectSerTicketProvider tests")

    def logout(self, session: SerProviderSession) -> None:
        self.logout_calls.append(session)
        if self._logout_error is not None:
            raise self._logout_error


class InMemoryUserSerProviderConfigRepo:
    def __init__(self) -> None:
        self.sessions: dict[tuple[UUID, str], SerProviderSession] = {}
        self.delete_calls: list[tuple[UUID, str]] = []

    def add(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        self.sessions[(user_id, provider)] = session

    def find(self, user_id: UUID, provider: str) -> SerProviderSession | None:
        return self.sessions.get((user_id, provider))

    def save(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        self.sessions[(user_id, provider)] = session

    def delete(self, user_id: UUID, provider: str) -> None:
        self.delete_calls.append((user_id, provider))
        self.sessions.pop((user_id, provider), None)

    def list_connected_providers(self, user_id: UUID) -> list[str]:
        return [provider for (uid, provider) in self.sessions if uid == user_id]


def test_successful_logout_returns_true_and_deletes_session() -> None:
    user_id = uuid4()
    provider = FakeSerTicketProvider()
    config_repo = InMemoryUserSerProviderConfigRepo()
    session = SerProviderSession(data={"access_token": "tok"})
    config_repo.add(user_id, "elparking", session)
    uc = DisconnectSerTicketProvider(providers={"elparking": provider}, config_repo=config_repo)

    result = uc.execute(user_id=user_id, provider="elparking")

    assert result is True
    assert provider.logout_calls == [session]
    assert config_repo.find(user_id, "elparking") is None
    assert config_repo.delete_calls == [(user_id, "elparking")]


def test_logout_failure_soft_fails_but_still_deletes_session() -> None:
    user_id = uuid4()
    provider = FakeSerTicketProvider(logout_error=SerProviderApiError("upstream failure"))
    config_repo = InMemoryUserSerProviderConfigRepo()
    config_repo.add(user_id, "elparking", SerProviderSession(data={"access_token": "tok"}))
    uc = DisconnectSerTicketProvider(providers={"elparking": provider}, config_repo=config_repo)

    result = uc.execute(user_id=user_id, provider="elparking")

    assert result is False
    assert config_repo.find(user_id, "elparking") is None
    assert config_repo.delete_calls == [(user_id, "elparking")]


def test_unregistered_provider_soft_fails_but_still_deletes_session() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserSerProviderConfigRepo()
    config_repo.add(user_id, "elparking", SerProviderSession(data={"access_token": "tok"}))
    uc = DisconnectSerTicketProvider(providers={}, config_repo=config_repo)

    result = uc.execute(user_id=user_id, provider="elparking")

    assert result is False
    assert config_repo.find(user_id, "elparking") is None
    assert config_repo.delete_calls == [(user_id, "elparking")]


def test_already_disconnected_is_a_no_op_success() -> None:
    user_id = uuid4()
    provider = FakeSerTicketProvider()
    config_repo = InMemoryUserSerProviderConfigRepo()
    uc = DisconnectSerTicketProvider(providers={"elparking": provider}, config_repo=config_repo)

    result = uc.execute(user_id=user_id, provider="elparking")

    assert result is True
    assert provider.logout_calls == []
    assert config_repo.delete_calls == []
