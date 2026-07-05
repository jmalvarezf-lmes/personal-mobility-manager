"""
Application use case: ConnectSerTicketProvider.

Resolves a named SER ticket provider from the registry, logs in with the
given credentials, and persists the resulting session for later ticket
creation. Not exposed over HTTP in this change — exercised only by unit
tests against a fake SerTicketProviderPort.
"""

from uuid import UUID

from mobility_manager.domain.exceptions import SerTicketProviderNotFoundError
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.ports.user_ser_provider_config_repository import (
    UserSerProviderConfigRepository,
)
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)


class ConnectSerTicketProvider:
    """Log in to a SER ticket provider on behalf of a user and persist the session."""

    def __init__(
        self,
        providers: dict[str, SerTicketProviderPort],
        config_repo: UserSerProviderConfigRepository,
    ) -> None:
        self._providers = providers
        self._config_repo = config_repo

    def execute(self, user_id: UUID, provider: str, credentials: SerProviderCredentials) -> None:
        """
        Log in to `provider` with `credentials` and persist the resulting session.

        Args:
            user_id: The user connecting their account.
            provider: Provider name to look up in the registry.
            credentials: Provider-defined login credentials.

        Raises:
            SerTicketProviderNotFoundError: If `provider` is not registered.
        """
        provider_instance = self._providers.get(provider)
        if provider_instance is None:
            raise SerTicketProviderNotFoundError(f"No SER ticket provider registered for {provider!r}")

        session = provider_instance.login(credentials)
        self._config_repo.save(user_id, provider, session)
