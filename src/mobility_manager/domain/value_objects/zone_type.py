"""
Domain: ZoneType base class.

Base class for city-specific parking zone type classifications. Each city
provider must subclass this and implement display_name and from_raw.

Not an ABC to avoid metaclass conflicts when combined with str+Enum in
city-specific implementations (EnumType and ABCMeta are not composable
without an explicit combined metaclass). The contract is enforced at
runtime via NotImplementedError.
"""

from __future__ import annotations


class ZoneType:
    """Base class for city-specific parking zone type classifications."""

    @property
    def display_name(self) -> str:
        """Human-readable zone type name stored in the DB and returned by the API."""
        raise NotImplementedError(f"'{type(self).__name__}' must implement display_name")

    @property
    def colour(self) -> str:
        """Hex colour string for map rendering. Defaults to grey for unknown types."""
        return "#6B7280"

    @classmethod
    def from_raw(cls, raw: str) -> ZoneType | None:
        """
        Parse a raw source string into a ZoneType instance.

        Returns None when the value is not recognised; the caller skips the row.
        """
        raise NotImplementedError(f"'{cls.__name__}' must implement from_raw")
