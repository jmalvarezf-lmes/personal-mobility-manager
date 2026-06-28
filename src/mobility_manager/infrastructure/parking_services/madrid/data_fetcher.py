"""
Infrastructure: MadridCallejeroCsvFetcher.

Downloads the Madrid Callejero CSV from the Madrid open data portal.
"""

import logging
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

_ALLOWED_HOSTNAMES = {"datos.madrid.es"}


class MadridCallejeroCsvFetcher:
    """Fetches the Madrid Callejero CSV via HTTP."""

    def __init__(self, url: str) -> None:
        self._url = url
        hostname = urlparse(url).hostname or ""
        if hostname not in _ALLOWED_HOSTNAMES:
            raise ValueError(f"URL hostname {hostname!r} is not in the allowed list: {_ALLOWED_HOSTNAMES}")

    def fetch(self) -> str:
        """
        Download the CSV and return its text content.

        Raises RuntimeError on non-2xx HTTP responses.
        """
        logger.info("Fetching Madrid Callejero CSV from %s", self._url)
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            response = client.get(self._url)

        if not response.is_success:
            raise RuntimeError(f"Failed to fetch Madrid Callejero CSV: HTTP {response.status_code}")

        logger.info("Fetched Madrid Callejero CSV (%d bytes)", len(response.content))
        # The Madrid callejero CSV is encoded in Latin-1 (ISO-8859-1).
        return response.content.decode("latin-1")
