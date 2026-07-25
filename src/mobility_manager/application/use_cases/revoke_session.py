"""
Application use case: RevokeSession.

Soft-revokes a server-side session on logout — see
add-session-revocation design.md.
"""

from uuid import UUID

from mobility_manager.domain.ports.session_repository import SessionRepository


class RevokeSession:
    """
    Revoke a session by id.

    Idempotent: the underlying SessionRepository.revoke() no-ops silently if
    the session doesn't exist, matching the existing logout idempotency
    (POST /auth/logout must succeed whether or not a live session exists).
    """

    def __init__(self, session_repo: SessionRepository) -> None:
        self._session_repo = session_repo

    def execute(self, session_id: UUID) -> None:
        """Revoke the session with the given id, if it exists."""
        self._session_repo.revoke(session_id)
