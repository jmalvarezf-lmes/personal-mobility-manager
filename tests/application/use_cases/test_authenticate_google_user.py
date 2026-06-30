"""
Unit tests for AuthenticateGoogleUser use case.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

from mobility_manager.application.use_cases.authenticate_google_user import (
    AuthenticateGoogleUser,
)
from mobility_manager.domain.entities.user import User


def _make_user(google_sub: str = "sub123", email: str = "user@example.com") -> User:
    return User(
        id=uuid4(),
        google_sub=google_sub,
        email=email,
        display_name="Test User",
        created_at=datetime.now(UTC),
    )


class TestAuthenticateGoogleUser:
    def test_calls_upsert_with_correct_args(self) -> None:
        mock_repo = MagicMock()
        expected_user = _make_user()
        mock_repo.upsert.return_value = expected_user

        uc = AuthenticateGoogleUser(user_repo=mock_repo)
        uc.execute(google_sub="sub123", email="user@example.com", display_name="Test User")

        mock_repo.upsert.assert_called_once_with(
            google_sub="sub123",
            email="user@example.com",
            display_name="Test User",
        )

    def test_returns_user_from_repo(self) -> None:
        mock_repo = MagicMock()
        expected_user = _make_user(google_sub="sub999", email="other@example.com")
        mock_repo.upsert.return_value = expected_user

        uc = AuthenticateGoogleUser(user_repo=mock_repo)
        result = uc.execute(
            google_sub="sub999",
            email="other@example.com",
            display_name="Other User",
        )

        assert result is expected_user

    def test_passes_display_name_through(self) -> None:
        mock_repo = MagicMock()
        mock_repo.upsert.return_value = _make_user()

        uc = AuthenticateGoogleUser(user_repo=mock_repo)
        uc.execute(google_sub="sub1", email="a@b.com", display_name="My Display Name")

        _, kwargs = mock_repo.upsert.call_args
        assert kwargs["display_name"] == "My Display Name"

    def test_upsert_called_once(self) -> None:
        mock_repo = MagicMock()
        mock_repo.upsert.return_value = _make_user()

        uc = AuthenticateGoogleUser(user_repo=mock_repo)
        uc.execute(google_sub="sub", email="e@e.com", display_name="Name")

        assert mock_repo.upsert.call_count == 1
