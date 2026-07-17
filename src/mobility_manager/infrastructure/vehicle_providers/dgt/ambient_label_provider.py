"""
Infrastructure: DgtAmbientLabelProvider.

Looks up a vehicle's DGT "distintivo ambiental" environmental label by
querying DGT's public HTML form and parsing the result. See
add-ambient-label-lookup design.md decisions 3 and 7:
hostname-allowlisted (mirroring MadridCallejeroCsvFetcher), the plate is
passed via httpx `params` (never string-concatenated into the URL), and the
client sends a standard browser User-Agent — not a custom/descriptive one.
"""

import logging
from urllib.parse import urljoin, urlparse

import httpx

from mobility_manager.domain.ports.ambient_label_lookup_port import (
    AmbientLabelLookupPort,
    VehicleAmbientLabelResult,
)
from mobility_manager.infrastructure.vehicle_providers.dgt.ambient_label_parser import (
    parse_ambient_label_response,
)

logger = logging.getLogger(__name__)

DEFAULT_DGT_AMBIENT_LABEL_URL = "https://sede.dgt.gob.es/es/vehiculos/informacion-de-vehiculos/distintivo-ambiental/index.html"

_ALLOWED_HOSTNAMES = {"sede.dgt.gob.es"}

# A standard browser User-Agent, not a custom/descriptive one (explicit
# product decision — see design.md decision 7). Traffic volume here is low
# (one request per vehicle needing a lookup, throttled to 5s apart) and the
# goal is a reliable response, not scraper transparency.
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class DgtAmbientLabelProvider(AmbientLabelLookupPort):
    """Queries DGT's public distintivo-ambiental form for a plate's environmental label."""

    def __init__(self, url: str = DEFAULT_DGT_AMBIENT_LABEL_URL, timeout: float = 30.0) -> None:
        """
        Args:
            url: DGT's distintivo-ambiental form URL. Hostname must be
                `sede.dgt.gob.es`.
            timeout: HTTP request timeout in seconds.

        Raises:
            ValueError: If the URL's hostname is not in the allowed list.
        """
        self._url = url
        self._timeout = timeout
        hostname = urlparse(url).hostname or ""
        if hostname not in _ALLOWED_HOSTNAMES:
            raise ValueError(f"URL hostname {hostname!r} is not in the allowed list: {_ALLOWED_HOSTNAMES}")

    def lookup(self, license_plate: str) -> VehicleAmbientLabelResult:
        """
        Fetch and parse DGT's response for the given plate.

        Raises:
            RuntimeError: On a non-2xx HTTP response.
            httpx.HTTPError: On a network error or timeout.

        The caller (LookupVehicleAmbientLabel) is responsible for catching
        both and mapping them to `status=error` (see design.md decision 4)
        — this method never swallows a failure itself.
        """
        logger.info("Looking up DGT ambient label for a vehicle plate")
        with httpx.Client(timeout=self._timeout, headers={"User-Agent": _USER_AGENT}) as client:
            response = client.get(self._url, params={"matricula": license_plate})

        if not response.is_success:
            raise RuntimeError(f"DGT ambient label lookup failed: HTTP {response.status_code}")

        return parse_ambient_label_response(response.text)

    def download_icon(self, icon_relative_url: str) -> tuple[bytes, str]:
        """
        Download the sticker icon referenced by a parsed relative URL.

        Resolves the relative path against the same allowlisted
        `sede.dgt.gob.es` host used for the lookup itself.

        Returns:
            A (image_bytes, content_type) tuple.

        Raises:
            ValueError: If the resolved icon URL's hostname is not allowed.
            RuntimeError: On a non-2xx HTTP response.
        """
        icon_url = urljoin(self._url, icon_relative_url)
        hostname = urlparse(icon_url).hostname or ""
        if hostname not in _ALLOWED_HOSTNAMES:
            raise ValueError(f"Icon URL hostname {hostname!r} is not in the allowed list: {_ALLOWED_HOSTNAMES}")

        with httpx.Client(timeout=self._timeout, headers={"User-Agent": _USER_AGENT}) as client:
            response = client.get(icon_url)

        if not response.is_success:
            raise RuntimeError(f"DGT icon download failed: HTTP {response.status_code}")

        content_type = response.headers.get("content-type", "image/svg+xml")
        return response.content, content_type
