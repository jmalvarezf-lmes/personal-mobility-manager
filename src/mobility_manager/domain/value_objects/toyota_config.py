"""
Domain value object: ToyotaConfig.

Holds Toyota-specific credentials used for pull-based location fetching.
Never persisted directly — serialised to JSON and AES-encrypted before storage.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class ToyotaConfig:
    """Toyota account credentials for pull-based location fetching."""

    username: str
    password: str
    locale: str
    vin: str
