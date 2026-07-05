"""
Domain value object: SerProviderSession.

Thin wrapper around a provider-defined session payload returned by
SerTicketProviderPort.login(). Mirrors ToyotaConfig's role: a named, typed
value crosses the port boundary rather than a bare dict. The exact shape
of `data` is opaque here since only one concrete provider is planned and
its payload isn't known yet.

Never persisted directly — the repository layer JSON-serialises and
Fernet-encrypts `data` before storage.
"""

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SerProviderSession:
    """Opaque, provider-defined session obtained from a SER ticket provider login."""

    data: dict[str, Any]
