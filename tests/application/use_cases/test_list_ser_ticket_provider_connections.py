"""
Unit tests for ListSerTicketProviderConnections use case.
"""

from uuid import UUID, uuid4

from mobility_manager.application.use_cases.list_ser_ticket_provider_connections import (
    ListSerTicketProviderConnections,
)


class InMemoryUserSerProviderConfigRepo:
    def __init__(self, connections: dict[UUID, list[str]] | None = None) -> None:
        self._connections = connections or {}

    def list_connected_providers(self, user_id: UUID) -> list[str]:
        return self._connections.get(user_id, [])


def test_reports_connected_providers() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserSerProviderConfigRepo({user_id: ["elparking"]})
    uc = ListSerTicketProviderConnections(config_repo=config_repo)

    assert uc.execute(user_id) == ["elparking"]


def test_reports_empty_list_when_no_connections() -> None:
    user_id = uuid4()
    config_repo = InMemoryUserSerProviderConfigRepo()
    uc = ListSerTicketProviderConnections(config_repo=config_repo)

    assert uc.execute(user_id) == []
