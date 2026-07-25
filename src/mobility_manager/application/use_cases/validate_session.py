"""
Application use case: ValidateSession.

Validates that a session referenced by a JWT's `sid` claim is still live —
see add-session-revocation design.md decision 2 (this replaces direct
repository access from deps.py for session validation).
"""

from datetime import UTC, datetime
from uuid import UUID

from mobility_manager.domain.ports.session_repository import SessionRepository


class ValidateSession:
    """
    Determine whether a session is valid: exists, not revoked, not expired,
    and owned by the given user.
    """

    def __init__(self, session_repo: SessionRepository) -> None:
        self._session_repo = session_repo

    def execute(self, session_id: UUID, user_id: UUID) -> bool:
        """
        Return True only if the session exists, revoked_at is None,
        expires_at is in the future, and session.user_id == user_id.
        """
        session = self._session_repo.find_by_id(session_id)
        if session is None:
            return False
        if session.revoked_at is not None:
            return False
        if session.expires_at <= datetime.now(UTC):
            return False
        return session.user_id == user_id
