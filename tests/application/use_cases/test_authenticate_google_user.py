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


def _make_use_case(user_repo=None, user_preferences_repo=None) -> AuthenticateGoogleUser:
    return AuthenticateGoogleUser(
        user_repo=user_repo or MagicMock(),
        user_preferences_repo=user_preferences_repo or MagicMock(),
    )


class TestAuthenticateGoogleUser:
    def test_calls_upsert_with_correct_args(self) -> None:
        mock_repo = MagicMock()
        expected_user = _make_user()
        mock_repo.upsert.return_value = expected_user

        uc = _make_use_case(user_repo=mock_repo)
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

        uc = _make_use_case(user_repo=mock_repo)
        result = uc.execute(
            google_sub="sub999",
            email="other@example.com",
            display_name="Other User",
        )

        assert result is expected_user

    def test_passes_display_name_through(self) -> None:
        mock_repo = MagicMock()
        mock_repo.upsert.return_value = _make_user()

        uc = _make_use_case(user_repo=mock_repo)
        uc.execute(google_sub="sub1", email="a@b.com", display_name="My Display Name")

        _, kwargs = mock_repo.upsert.call_args
        assert kwargs["display_name"] == "My Display Name"

    def test_upsert_called_once(self) -> None:
        mock_repo = MagicMock()
        mock_repo.upsert.return_value = _make_user()

        uc = _make_use_case(user_repo=mock_repo)
        uc.execute(google_sub="sub", email="e@e.com", display_name="Name")

        assert mock_repo.upsert.call_count == 1

    def test_ensure_default_called_with_upserted_user_id(self) -> None:
        mock_repo = MagicMock()
        expected_user = _make_user()
        mock_repo.upsert.return_value = expected_user
        mock_preferences_repo = MagicMock()

        uc = _make_use_case(user_repo=mock_repo, user_preferences_repo=mock_preferences_repo)
        uc.execute(google_sub="sub123", email="user@example.com", display_name="Test User")

        mock_preferences_repo.ensure_default.assert_called_once_with(expected_user.id)

    def test_ensure_default_called_after_upsert(self) -> None:
        mock_repo = MagicMock()
        mock_repo.upsert.return_value = _make_user()
        mock_preferences_repo = MagicMock()

        call_order: list[str] = []
        mock_repo.upsert.side_effect = lambda **_: (call_order.append("upsert"), mock_repo.upsert.return_value)[1]
        mock_preferences_repo.ensure_default.side_effect = lambda _: call_order.append("ensure_default")

        uc = _make_use_case(user_repo=mock_repo, user_preferences_repo=mock_preferences_repo)
        uc.execute(google_sub="sub", email="e@e.com", display_name="Name")

        assert call_order == ["upsert", "ensure_default"]
