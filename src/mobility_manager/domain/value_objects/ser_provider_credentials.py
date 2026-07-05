"""
Domain value object: SerProviderCredentials.

Thin wrapper around a provider-defined credentials payload used to log in
to a SER ticket provider. Mirrors ToyotaConfig's role: a named, typed value
crosses the port boundary rather than a bare dict. The exact shape of
`data` is opaque here since only one concrete provider is planned and its
payload isn't known yet.

Never persisted directly — the repository layer JSON-serialises and
Fernet-encrypts `data` before storage.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SerProviderCredentials:
    """Opaque, provider-defined login credentials for a SER ticket provider."""

    data: dict[str, Any]
