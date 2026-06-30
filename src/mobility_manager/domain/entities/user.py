"""
Domain entity: User.

Represents a user authenticated via Google OAuth2.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class User:
    """Core user entity — identified by Google sub claim."""

    id: UUID
    google_sub: str
    email: str
    display_name: str
    created_at: datetime
