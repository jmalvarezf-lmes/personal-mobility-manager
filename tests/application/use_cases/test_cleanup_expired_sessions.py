"""Unit tests for CleanupExpiredSessions use case."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

from mobility_manager.application.use_cases.cleanup_expired_sessions import (
    CleanupExpiredSessions,
)


class TestCleanupExpiredSessions:
    def test_computes_cutoff_from_configured_retention_days(self) -> None:
        mock_repo = MagicMock()
        mock_repo.delete_older_than.return_value = 3

        uc = CleanupExpiredSessions(session_repo=mock_repo, retention_days=30)
        uc.execute()

        mock_repo.delete_older_than.assert_called_once()
        (cutoff,), _ = mock_repo.delete_older_than.call_args
        expected_cutoff = datetime.now(UTC) - timedelta(days=30)
        assert abs((cutoff - expected_cutoff).total_seconds()) < 5

    def test_returns_deleted_count(self) -> None:
        mock_repo = MagicMock()
        mock_repo.delete_older_than.return_value = 7

        uc = CleanupExpiredSessions(session_repo=mock_repo, retention_days=30)
        result = uc.execute()

        assert result == 7

    def test_uses_custom_retention_days(self) -> None:
        mock_repo = MagicMock()
        mock_repo.delete_older_than.return_value = 0

        uc = CleanupExpiredSessions(session_repo=mock_repo, retention_days=7)
        uc.execute()

        (cutoff,), _ = mock_repo.delete_older_than.call_args
        expected_cutoff = datetime.now(UTC) - timedelta(days=7)
        assert abs((cutoff - expected_cutoff).total_seconds()) < 5
