"""
Application use case: CleanupExpiredSessions.

Purges revoked/expired session rows older than a configurable retention
window — see add-session-revocation design.md decisions 3 and 6.
"""

import logging
from datetime import UTC, datetime, timedelta

from mobility_manager.domain.ports.session_repository import SessionRepository

logger = logging.getLogger(__name__)


class CleanupExpiredSessions:
    """Delete sessions rows whose revoked_at/expires_at predate the retention window."""

    def __init__(self, session_repo: SessionRepository, retention_days: int) -> None:
        self._session_repo = session_repo
        self._retention_days = retention_days

    def execute(self) -> int:
        """
        Compute the retention cutoff and delete rows older than it.

        Returns the number of rows deleted, for scheduler-side logging.
        """
        cutoff = datetime.now(UTC) - timedelta(days=self._retention_days)
        deleted = self._session_repo.delete_older_than(cutoff)
        logger.info("Session cleanup deleted %d row(s) older than %s", deleted, cutoff)
        return deleted
