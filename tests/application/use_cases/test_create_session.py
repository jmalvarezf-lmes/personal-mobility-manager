"""Unit tests for CreateSession use case."""

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock
from uuid import uuid4

from mobility_manager.application.use_cases.create_session import CreateSession
from mobility_manager.domain.entities.session import Session


def _make_session(user_id, expires_at) -> Session:
    now = datetime.now(UTC)
    return Session(
        id=uuid4(),
        user_id=user_id,
        created_at=now,
        expires_at=expires_at,
        revoked_at=None,
    )


class TestCreateSession:
    def test_calls_repo_create_with_user_id_and_future_expires_at(self) -> None:
        mock_repo = MagicMock()
        user_id = uuid4()
        mock_repo.create.return_value = _make_session(user_id, datetime.now(UTC) + timedelta(hours=24))

        uc = CreateSession(session_repo=mock_repo)
        uc.execute(user_id=user_id)

        mock_repo.create.assert_called_once()
        _, kwargs = mock_repo.create.call_args
        assert kwargs["user_id"] == user_id
        assert kwargs["expires_at"] > datetime.now(UTC)

    def test_expires_at_is_roughly_24_hours_from_now(self) -> None:
        mock_repo = MagicMock()
        user_id = uuid4()
        mock_repo.create.return_value = _make_session(user_id, datetime.now(UTC) + timedelta(hours=24))

        uc = CreateSession(session_repo=mock_repo)
        uc.execute(user_id=user_id)

        _, kwargs = mock_repo.create.call_args
        delta = kwargs["expires_at"] - datetime.now(UTC)
        assert timedelta(hours=23, minutes=59) < delta <= timedelta(hours=24, minutes=1)

    def test_returns_session_from_repo(self) -> None:
        mock_repo = MagicMock()
        user_id = uuid4()
        expected_session = _make_session(user_id, datetime.now(UTC) + timedelta(hours=24))
        mock_repo.create.return_value = expected_session

        uc = CreateSession(session_repo=mock_repo)
        result = uc.execute(user_id=user_id)

        assert result is expected_session
