"""
Domain value object: Brand.

Closed enum of supported vehicle brands. New brands require code changes.
"""

from enum import StrEnum


class Brand(StrEnum):
    """Supported vehicle brands."""

    TOYOTA = "toyota"
    GENERIC = "generic"
