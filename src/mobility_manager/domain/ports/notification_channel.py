"""
Port (interface): NotificationChannelPort.

Abstract, channel-agnostic contract for sending a notification. Deliberately
carries a single abstract method — unlike SerTicketProviderPort's
login/create_ticket/logout trio, there is no shared "connect" concept here:
a channel's account-linking mechanism (e.g. Telegram's deep-link flow) is
entirely channel-specific and lives in that channel's own
application/infrastructure code, not on this port. A future WhatsApp
implementation might need no linking flow at all.
"""

from abc import ABC, abstractmethod

from mobility_manager.domain.value_objects.notification_message import (
    NotificationMessage,
)
from mobility_manager.domain.value_objects.notification_recipient import (
    NotificationRecipient,
)


class NotificationChannelPort(ABC):
    """Abstract notification channel — implemented per channel in infrastructure."""

    @abstractmethod
    def send(self, recipient: NotificationRecipient, message: NotificationMessage) -> None:
        """
        Deliver `message` to `recipient` via this channel.

        Raises:
            NotificationChannelApiError: The channel's API call failed
                (network error, unexpected status).
        """
        ...
