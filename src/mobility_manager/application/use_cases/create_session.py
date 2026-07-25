"""
Application use case: CreateSession.

Creates a new server-side session for a user on login — see
add-session-revocation design.md.
"""

from datetime import UTC, datetime
from uuid import UUID

from mobility_manager.config import SESSION_LIFETIME
from mobility_manager.domain.entities.session import Session
from mobility_manager.domain.ports.session_repository import SessionRepository


class CreateSession:
    """Create a new session for a user, valid for 24 hours from now."""

    def __init__(self, session_repo: SessionRepository) -> None:
        self._session_repo = session_repo

    def execute(self, user_id: UUID) -> Session:
        """
        Create and persist a new session for user_id.

        Computes expires_at as now + SESSION_LIFETIME (matching the JWT's
        own lifetime — see config.SESSION_LIFETIME, the single source of
        truth shared with auth.py) and delegates persistence to the
        SessionRepository port.
        """
        expires_at = datetime.now(UTC) + SESSION_LIFETIME
        return self._session_repo.create(user_id=user_id, expires_at=expires_at)
