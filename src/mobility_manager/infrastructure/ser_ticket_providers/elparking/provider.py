"""
Infrastructure: ElParkingSerTicketProvider.

Implements SerTicketProviderPort.login() against ElParking's POST /v1/logins
endpoint using a synchronous httpx.Client — mirroring
MadridCallejeroCsvFetcher.fetch()'s sync-client style rather than the async
httpx.AsyncClient pattern used in the OAuth callback route. There is no async
requirement here: SerTicketProviderPort.login is a plain synchronous method.

create_ticket() is a deliberate NotImplementedError stub — ElParking's
ticket-creation API spec is not yet available and lands in a separate future
change.
"""

import logging
from typing import Any

import httpx

from mobility_manager.config import get_elparking_app_version, get_elparking_base_url
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderAuthenticationError,
)
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)

logger = logging.getLogger(__name__)

# ep-app-name isn't deployment config — it's a fixed characteristic of how
# this specific provider class identifies itself to the API — so it stays a
# hardcoded constant. "elparking" is the most semantically correct of the
# three valid ep-app-name values (parkingdoor, elparking, plock) for
# identifying as the ElParking client itself.
_EP_APP_NAME = "elparking"

# Unlike ep-app-name, the app version is expected to evolve over time as this
# integration matures, so it's read from ELPARKING_APP_VERSION (see
# config.get_elparking_app_version()) rather than hardcoded.

_LOGIN_TIMEOUT_SECONDS = 15.0

# ASSUMPTION — UNVERIFIED AGAINST THE LIVE API (see tasks.md 8.3):
# ElParking's available documentation describes the happy path and the
# ep-app-name domain-check 403, but does not specify the exact status code
# returned for rejected credentials. 401 Unauthorized is the conventional
# choice for "bad email/password" on a login endpoint, so it is used here as
# a single, isolated, easy-to-change signal. If real-API testing (task 8.3)
# reveals a different code (e.g. 422), update only this constant.
_INVALID_CREDENTIALS_STATUS_CODE = 401


class ElParkingSerTicketProvider(SerTicketProviderPort):
    """SER ticket provider backed by ElParking's REST API."""

    def __init__(self) -> None:
        # Fails fast if ELPARKING_API_BASE_URL is unset — in practice this is
        # already validated by SerTicketProviderRegistry before instantiation,
        # but resolving it here keeps the provider self-contained and safe to
        # construct directly (e.g. in tests).
        self._base_url = get_elparking_base_url()

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        """
        Authenticate with ElParking and return a minimal session.

        Args:
            credentials: Must contain "email" and "password" in `.data`;
                "uid" and "model" are included in the request body when
                present.

        Returns:
            A SerProviderSession whose `data` contains exactly
            `{"access_token": str, "device_session_id": int}`.

        Raises:
            SerProviderAuthenticationError: ElParking rejected the credentials.
            SerProviderApiError: Any other failure — network error, timeout,
                unexpected status code, or a malformed response body.
        """
        body: dict[str, Any] = {
            "email": credentials.data["email"],
            "password": credentials.data["password"],
        }
        if "uid" in credentials.data:
            body["uid"] = credentials.data["uid"]
        if "model" in credentials.data:
            body["model"] = credentials.data["model"]

        headers = {
            "Content-Type": "application/json",
            "ep-app-name": _EP_APP_NAME,
            "ep-app-version": get_elparking_app_version(),
        }

        try:
            with httpx.Client(timeout=_LOGIN_TIMEOUT_SECONDS) as client:
                response = client.post(f"{self._base_url}/v1/logins", json=body, headers=headers)
        except httpx.HTTPError as exc:
            raise SerProviderApiError(f"ElParking login request failed: {exc}") from exc

        if response.status_code == _INVALID_CREDENTIALS_STATUS_CODE:
            raise SerProviderAuthenticationError("ElParking rejected the provided credentials")

        if not response.is_success:
            raise SerProviderApiError(
                f"ElParking login returned unexpected status {response.status_code}: {response.text[:200]}"
            )

        try:
            payload = response.json()
            access_token = payload["access_token"]
            device_session_id = payload["id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise SerProviderApiError(f"ElParking login returned an unexpected response body: {exc}") from exc

        return SerProviderSession(data={"access_token": access_token, "device_session_id": device_session_id})

    def create_ticket(self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int) -> ParkingTicket:
        """Not yet implemented — ElParking's ticket-creation API spec isn't available yet."""
        raise NotImplementedError("ElParking ticket creation is not yet implemented")
