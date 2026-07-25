"""Unit tests for RevokeSession use case."""

from unittest.mock import MagicMock
from uuid import uuid4

from mobility_manager.application.use_cases.revoke_session import RevokeSession


class TestRevokeSession:
    def test_calls_repo_revoke_with_session_id(self) -> None:
        mock_repo = MagicMock()
        session_id = uuid4()

        uc = RevokeSession(session_repo=mock_repo)
        uc.execute(session_id=session_id)

        mock_repo.revoke.assert_called_once_with(session_id)

    def test_no_exception_when_session_does_not_exist(self) -> None:
        mock_repo = MagicMock()
        mock_repo.revoke.return_value = None  # repo no-ops silently

        uc = RevokeSession(session_repo=mock_repo)

        # Must not raise.
        uc.execute(session_id=uuid4())
