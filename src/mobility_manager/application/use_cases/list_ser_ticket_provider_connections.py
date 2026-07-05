"""
Application use case: ListSerTicketProviderConnections.

Thin delegation to UserSerProviderConfigRepository.list_connected_providers,
reporting which SER ticket providers a user currently has a stored session for.
"""

from uuid import UUID

from mobility_manager.domain.ports.user_ser_provider_config_repository import (
    UserSerProviderConfigRepository,
)


class ListSerTicketProviderConnections:
    """Report which SER ticket providers a user has connected."""

    def __init__(self, config_repo: UserSerProviderConfigRepository) -> None:
        self._config_repo = config_repo

    def execute(self, user_id: UUID) -> list[str]:
        """Return the provider names for which `user_id` has a stored session."""
        return self._config_repo.list_connected_providers(user_id)
