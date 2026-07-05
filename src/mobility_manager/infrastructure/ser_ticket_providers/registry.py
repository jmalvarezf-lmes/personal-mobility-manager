"""
Infrastructure: SerTicketProviderRegistry.

Mirrors infrastructure/vehicle_providers/brand_registry.py's shape: a
registry class returning the currently available SerTicketProviderPort
implementations, keyed by provider name.

Returns an empty mapping today since no concrete provider exists yet —
this is expected, valid behavior, not an error condition (mirrors
BrandRegistry, which is also infrastructure-only with no domain port).
"""

from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort


class SerTicketProviderRegistry:
    """Returns the mapping of currently available SerTicketProviderPort implementations."""

    def build_providers(self) -> dict[str, SerTicketProviderPort]:
        """
        Instantiate every registered SER ticket provider, keyed by provider name.

        Returns an empty dict when no concrete provider is registered — callers
        must treat this as an expected, handleable condition rather than an error.
        """
        return {}
