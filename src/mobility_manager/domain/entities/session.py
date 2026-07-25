"""
Domain entity: Session.

Represents one server-side login session for a User, used as the source of
truth for session liveness (see add-session-revocation design.md).
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Session:
    """Core session entity — one row per login, tracked independently of the JWT."""

    id: UUID
    user_id: UUID
    created_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
