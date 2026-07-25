"""Unit tests for Session entity."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from mobility_manager.domain.entities.session import Session


def _make_session(**kwargs) -> Session:
    now = datetime.now(UTC)
    defaults = {
        "id": uuid4(),
        "user_id": uuid4(),
        "created_at": now,
        "expires_at": now + timedelta(hours=24),
        "revoked_at": None,
    }
    defaults.update(kwargs)
    return Session(**defaults)


def test_session_construction_with_fields() -> None:
    session_id = uuid4()
    user_id = uuid4()
    now = datetime.now(UTC)
    expires_at = now + timedelta(hours=24)

    session = Session(
        id=session_id,
        user_id=user_id,
        created_at=now,
        expires_at=expires_at,
        revoked_at=None,
    )

    assert session.id == session_id
    assert session.user_id == user_id
    assert session.created_at == now
    assert session.expires_at == expires_at
    assert session.revoked_at is None


def test_session_can_carry_a_revoked_at_timestamp() -> None:
    revoked_at = datetime.now(UTC)
    session = _make_session(revoked_at=revoked_at)
    assert session.revoked_at == revoked_at


def test_session_is_immutable() -> None:
    session = _make_session()
    with pytest.raises((AttributeError, TypeError)):
        session.revoked_at = datetime.now(UTC)  # type: ignore[misc]
