"""Unit tests for ValidateSession use case."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from mobility_manager.application.use_cases.validate_session import ValidateSession
from mobility_manager.domain.entities.session import Session


def _make_session(user_id, *, revoked: bool, expired: bool) -> Session:
    now = datetime.now(UTC)
    return Session(
        id=uuid4(),
        user_id=user_id,
        created_at=now - timedelta(hours=1),
        expires_at=now - timedelta(hours=1) if expired else now + timedelta(hours=23),
        revoked_at=now if revoked else None,
    )


class TestValidateSession:
    def test_live_session_is_valid(self) -> None:
        user_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = _make_session(user_id, revoked=False, expired=False)

        uc = ValidateSession(session_repo=mock_repo)
        assert uc.execute(session_id=uuid4(), user_id=user_id) is True

    def test_revoked_session_is_invalid(self) -> None:
        user_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = _make_session(user_id, revoked=True, expired=False)

        uc = ValidateSession(session_repo=mock_repo)
        assert uc.execute(session_id=uuid4(), user_id=user_id) is False

    def test_missing_session_is_invalid(self) -> None:
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = None

        uc = ValidateSession(session_repo=mock_repo)
        assert uc.execute(session_id=uuid4(), user_id=uuid4()) is False

    def test_expired_session_is_invalid(self) -> None:
        user_id = uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = _make_session(user_id, revoked=False, expired=True)

        uc = ValidateSession(session_repo=mock_repo)
        assert uc.execute(session_id=uuid4(), user_id=user_id) is False

    def test_user_id_mismatch_is_invalid(self) -> None:
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = _make_session(uuid4(), revoked=False, expired=False)

        uc = ValidateSession(session_repo=mock_repo)
        assert uc.execute(session_id=uuid4(), user_id=uuid4()) is False

    @pytest.mark.parametrize(
        ("revoked", "expired", "matching_user", "expected"),
        [
            (False, False, True, True),
            (True, False, True, False),
            (False, False, False, False),
        ],
    )
    def test_table_of_cases(self, revoked: bool, expired: bool, matching_user: bool, expected: bool) -> None:
        session_user_id = uuid4()
        lookup_user_id = session_user_id if matching_user else uuid4()
        mock_repo = MagicMock()
        mock_repo.find_by_id.return_value = _make_session(session_user_id, revoked=revoked, expired=expired)

        uc = ValidateSession(session_repo=mock_repo)
        assert uc.execute(session_id=uuid4(), user_id=lookup_user_id) is expected
