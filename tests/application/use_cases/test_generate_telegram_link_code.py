"""
Unit tests for GenerateTelegramLinkCode use case.
"""

from uuid import uuid4

import pytest

from mobility_manager.application.use_cases.generate_telegram_link_code import (
    GenerateTelegramLinkCode,
)
from mobility_manager.infrastructure.telegram_link import verify_link_token

_JWT_SECRET = "test-secret-for-generate-telegram-link-code"


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)


def test_execute_returns_a_token_decodable_to_the_same_user_id() -> None:
    user_id = uuid4()
    uc = GenerateTelegramLinkCode()

    token = uc.execute(user_id)

    assert verify_link_token(token) == user_id
