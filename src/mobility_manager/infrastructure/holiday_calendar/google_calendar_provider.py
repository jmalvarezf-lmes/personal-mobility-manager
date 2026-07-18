"""
Infrastructure: GoogleCalendarHolidayProvider.

Fetches Spain's national public holiday calendar from Google Calendar's
public iCal feed, returning the raw `.ics` text unparsed. Mirrors the
existing provider pattern (`DgtAmbientLabelProvider`/`MadridCallejeroCsvFetcher`)
— see add-ser-enforcement-calendar design.md D7/D11: hostname-allowlisted,
`httpx` fetch with a standard browser User-Agent, raises on non-2xx/network
errors rather than swallowing them itself.

Parsing (and the per-city filtering it requires — see
`ical_holiday_parser.parse_ical_holidays`) is deliberately not done here:
the provider performs exactly one HTTP GET per refresh run regardless of
how many cities are configured, and the caller (`RefreshPublicHolidays`)
parses the same raw text once per enabled city.
"""

import logging
from urllib.parse import urlparse

import httpx

from mobility_manager.domain.ports.public_holiday_provider import PublicHolidayProvider

logger = logging.getLogger(__name__)

DEFAULT_HOLIDAY_ICAL_URL = (
    "https://calendar.google.com/calendar/ical/es.spain%23holiday%40group.v.calendar.google.com/public/basic.ics"
)

_ALLOWED_HOSTNAMES = {"calendar.google.com"}

# A standard browser User-Agent, not a custom/descriptive one — matches
# DgtAmbientLabelProvider's product decision (see its module docstring,
# referencing add-ambient-label-lookup design.md decision 7).
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class GoogleCalendarHolidayProvider(PublicHolidayProvider):
    """Fetches and parses Spain's national holiday calendar from Google Calendar's public iCal feed."""

    def __init__(self, url: str = DEFAULT_HOLIDAY_ICAL_URL, timeout: float = 30.0) -> None:
        """
        Args:
            url: Google Calendar iCal feed URL. Hostname must be
                `calendar.google.com`.
            timeout: HTTP request timeout in seconds.

        Raises:
            ValueError: If the URL's hostname is not in the allowed list.
        """
        self._url = url
        self._timeout = timeout
        hostname = urlparse(url).hostname or ""
        if hostname not in _ALLOWED_HOSTNAMES:
            raise ValueError(f"URL hostname {hostname!r} is not in the allowed list: {_ALLOWED_HOSTNAMES}")

    def fetch_raw_calendar(self) -> str:
        """
        Fetch the raw `.ics` calendar text, unparsed.

        Raises:
            RuntimeError: On a non-2xx HTTP response.
            httpx.HTTPError: On a network error or timeout.

        The caller (RefreshPublicHolidays) is responsible for catching both
        and logging without crashing the scheduler — this method never
        swallows a failure itself.
        """
        logger.info("Fetching national holiday calendar from %s", self._url)
        with httpx.Client(timeout=self._timeout, headers={"User-Agent": _USER_AGENT}) as client:
            response = client.get(self._url)

        if not response.is_success:
            raise RuntimeError(f"Holiday calendar fetch failed: HTTP {response.status_code}")

        return response.text
