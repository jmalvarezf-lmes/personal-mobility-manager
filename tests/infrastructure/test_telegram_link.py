"""
Unit tests for generate_link_token / verify_link_token.
"""

import time
from uuid import uuid4

import pytest
from itsdangerous import URLSafeTimedSerializer

from mobility_manager.infrastructure.telegram_link import (
    generate_link_token,
    verify_link_token,
)

_JWT_SECRET = "test-secret-for-telegram-link"


@pytest.fixture(autouse=True)
def _jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("JWT_SECRET", _JWT_SECRET)


def test_generate_then_verify_round_trips_user_id() -> None:
    user_id = uuid4()

    token = generate_link_token(user_id)

    assert verify_link_token(token) == user_id


def test_expired_token_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = uuid4()
    token = generate_link_token(user_id)

    real_time = time.time

    monkeypatch.setattr(time, "time", lambda: real_time() + 601)

    with pytest.raises(ValueError):
        verify_link_token(token)


def test_tampered_token_raises_value_error() -> None:
    user_id = uuid4()
    token = generate_link_token(user_id)
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(ValueError):
        verify_link_token(tampered)


def test_token_signed_with_a_different_salt_is_rejected() -> None:
    user_id = uuid4()
    other_serializer = URLSafeTimedSerializer(_JWT_SECRET, salt="oauth2-state")
    token = other_serializer.dumps({"user_id": str(user_id)})

    with pytest.raises(ValueError):
        verify_link_token(token)
