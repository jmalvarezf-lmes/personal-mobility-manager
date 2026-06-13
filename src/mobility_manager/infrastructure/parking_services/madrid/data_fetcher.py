"""
Infrastructure: MadridCallejeroCsvFetcher.

Downloads the Madrid Callejero CSV from the Madrid open data portal.
"""
import logging

import httpx

logger = logging.getLogger(__name__)


class MadridCallejeroCsvFetcher:
    """Fetches the Madrid Callejero CSV via HTTP."""

    def __init__(self, url: str) -> None:
        self._url = url

    def fetch(self) -> str:
        """
        Download the CSV and return its text content.

        Raises RuntimeError on non-2xx HTTP responses.
        """
        logger.info("Fetching Madrid Callejero CSV from %s", self._url)
        with httpx.Client(follow_redirects=True, timeout=60.0) as client:
            response = client.get(self._url)

        if not response.is_success:
            raise RuntimeError(
                f"Failed to fetch Madrid Callejero CSV: HTTP {response.status_code}"
            )

        logger.info(
            "Fetched Madrid Callejero CSV (%d bytes)", len(response.content)
        )
        # The Madrid callejero CSV is encoded in Latin-1 (ISO-8859-1).
        return response.content.decode("latin-1")
