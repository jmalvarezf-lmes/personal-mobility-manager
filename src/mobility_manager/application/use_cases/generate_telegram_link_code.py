"""
Application use case: GenerateTelegramLinkCode.

Issues a signed, time-limited Telegram linking token for a user. Does not
build the full t.me deep-link URL — that's a presentation-layer concern
(needs the bot's @username and HTTP-level URL construction), mirroring how
other use cases stay free of HTTP-level concepts.
"""

from uuid import UUID

from mobility_manager.infrastructure.telegram_link import generate_link_token


class GenerateTelegramLinkCode:
    """Generate a signed, time-limited Telegram account-linking token."""

    def execute(self, user_id: UUID) -> str:
        """Return a signed, time-limited token identifying `user_id`."""
        return generate_link_token(user_id)
