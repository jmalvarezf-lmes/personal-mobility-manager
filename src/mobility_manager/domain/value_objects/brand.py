"""
Domain value object: Brand.

Closed enum of supported vehicle brands. New brands require code changes.
"""
from enum import Enum


class Brand(str, Enum):
    """Supported vehicle brands."""

    TOYOTA = "toyota"
    GENERIC = "generic"
