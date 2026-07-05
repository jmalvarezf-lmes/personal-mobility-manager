"""
Application use case: DisconnectSerTicketProvider.

Removes a user's stored SER ticket provider session, attempting a
best-effort provider-side logout that never blocks the local deletion.
"""

from uuid import UUID

from mobility_manager.domain.exceptions import SerProviderApiError
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.ports.user_ser_provider_config_repository import (
    UserSerProviderConfigRepository,
)


class DisconnectSerTicketProvider:
    """Disconnect a user's SER ticket provider account, deleting the local session unconditionally."""

    def __init__(
        self,
        providers: dict[str, SerTicketProviderPort],
        config_repo: UserSerProviderConfigRepository,
    ) -> None:
        self._providers = providers
        self._config_repo = config_repo

    def execute(self, user_id: UUID, provider: str) -> bool:
        """
        Disconnect `provider` for `user_id`.

        Args:
            user_id: The user disconnecting their account.
            provider: Provider name to disconnect.

        Returns:
            Whether the provider-side logout succeeded. `True` if there was
            no session to begin with (idempotent no-op), if the provider
            confirmed the logout, or `False` if the provider instance is
            unregistered or the logout call itself failed. The local session
            is always deleted regardless of this outcome, except when there
            was nothing to delete in the first place.
        """
        session = self._config_repo.find(user_id, provider)
        if session is None:
            return True

        logout_succeeded = True
        provider_instance = self._providers.get(provider)
        if provider_instance is None:
            logout_succeeded = False
        else:
            try:
                provider_instance.logout(session)
            except SerProviderApiError:
                logout_succeeded = False

        self._config_repo.delete(user_id, provider)
        return logout_succeeded
