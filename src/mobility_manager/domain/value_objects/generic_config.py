"""
Domain value object: GenericConfig.

Holds the push-endpoint token for generic (non-Toyota) vehicles.
Stored as cleartext because the token is not user-identifiable.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GenericConfig:
    """Configuration for a generic (push-only) vehicle."""

    location_token: str
