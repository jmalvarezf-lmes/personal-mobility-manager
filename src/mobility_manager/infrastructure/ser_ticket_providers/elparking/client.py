"""
Infrastructure: ElParkingClient.

Centralizes every ElParking HTTP call (login, logout, list vehicles, list SER
towns, list a town's zones, fetch pricing/checksum steps, create a ticket)
behind one httpx.Client-based class, mirroring MadridCallejeroCsvFetcher's
sync-client style rather than the async httpx.AsyncClient pattern used
elsewhere.

Every authenticated call (all except login) uses HTTP Basic auth with a
blank username and the session's access_token as the password — not an
Authorization: Bearer header — plus the same ep-app-name/ep-app-version
headers login() sends. This is the corrected auth scheme confirmed by the
user for logout and every new endpoint added by this change; see
provider.py's former (now removed) ASSUMPTION note for the pre-fix history.
"""

import logging
from typing import Any

import httpx

from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderAuthenticationError,
)
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)

logger = logging.getLogger(__name__)

# ep-app-name isn't deployment config — it's a fixed characteristic of how
# this specific client identifies itself to the API — so it stays a
# hardcoded constant. "elparking" is the most semantically correct of the
# three valid ep-app-name values (parkingdoor, elparking, plock) for
# identifying as the ElParking client itself.
_EP_APP_NAME = "elparking"

_LOGIN_TIMEOUT_SECONDS = 15.0
_LOGOUT_TIMEOUT_SECONDS = 15.0
_DEFAULT_TIMEOUT_SECONDS = 15.0
_CREATE_TICKET_TIMEOUT_SECONDS = 20.0

# ASSUMPTION — UNVERIFIED AGAINST THE LIVE API (see tasks.md 10.3):
# ElParking's available documentation describes the happy path and the
# ep-app-name domain-check 403, but does not specify the exact status code
# returned for rejected credentials. 401 Unauthorized is the conventional
# choice for "bad email/password" on a login endpoint, so it is used here as
# a single, isolated, easy-to-change signal. If real-API testing reveals a
# different code (e.g. 422), update only this constant.
_INVALID_CREDENTIALS_STATUS_CODE = 401


class ElParkingClient:
    """Thin wrapper around every ElParking HTTP call, with correct authentication."""

    def __init__(self, base_url: str, app_version: str) -> None:
        self._base_url = base_url
        self._app_version = app_version

    def _auth_headers(self) -> dict[str, str]:
        """Headers required on every call (including login) — ep-app-name/ep-app-version."""
        return {"ep-app-name": _EP_APP_NAME, "ep-app-version": self._app_version}

    def _basic_auth(self, access_token: str) -> httpx.BasicAuth:
        """HTTP Basic auth with a blank username and `access_token` as the password."""
        return httpx.BasicAuth("", access_token)

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        """
        Authenticate with ElParking and return a minimal session.

        Moved from ElParkingSerTicketProvider.login() unchanged in behavior.

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

        headers = {"Content-Type": "application/json", **self._auth_headers()}

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

    def logout(self, access_token: str) -> None:
        """
        Invalidate a session via DELETE /v1/logins/{access_token}.

        Raises:
            SerProviderApiError: Network error, timeout, or a non-2xx response.
        """
        headers = self._auth_headers()

        try:
            with httpx.Client(timeout=_LOGOUT_TIMEOUT_SECONDS) as client:
                response = client.delete(
                    f"{self._base_url}/v1/logins/{access_token}",
                    headers=headers,
                    auth=self._basic_auth(access_token),
                )
        except httpx.HTTPError as exc:
            raise SerProviderApiError(f"ElParking logout request failed: {exc}") from exc

        if not response.is_success:
            raise SerProviderApiError(
                f"ElParking logout returned unexpected status {response.status_code}: {response.text[:200]}"
            )

    def _authenticated_get(self, access_token: str, path: str) -> Any:
        """Shared GET helper for every authenticated read call below."""
        try:
            with httpx.Client(timeout=_DEFAULT_TIMEOUT_SECONDS) as client:
                response = client.get(
                    f"{self._base_url}{path}",
                    headers=self._auth_headers(),
                    auth=self._basic_auth(access_token),
                )
        except httpx.HTTPError as exc:
            raise SerProviderApiError(f"ElParking request to {path} failed: {exc}") from exc

        if not response.is_success:
            raise SerProviderApiError(
                f"ElParking {path} returned unexpected status {response.status_code}: {response.text[:200]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise SerProviderApiError(f"ElParking {path} returned a non-JSON response body: {exc}") from exc

    def list_vehicles(self, access_token: str) -> list[dict[str, Any]]:
        """GET /v1/users/me/vehicles — the authenticated user's registered vehicles."""
        payload = self._authenticated_get(access_token, "/v1/users/me/vehicles")
        if not isinstance(payload, list):
            raise SerProviderApiError("ElParking vehicle list returned an unexpected shape")
        return payload

    def list_towns(self, access_token: str) -> list[dict[str, Any]]:
        """GET /v1/ser-towns — every SER town ElParking knows about."""
        payload = self._authenticated_get(access_token, "/v1/ser-towns")
        if not isinstance(payload, list):
            raise SerProviderApiError("ElParking town list returned an unexpected shape")
        return payload

    def list_zones(self, access_token: str, town_id: str) -> list[dict[str, Any]]:
        """GET /v1/ser-zones/<townId> — every SER zone within a town."""
        payload = self._authenticated_get(access_token, f"/v1/ser-zones/{town_id}")
        if not isinstance(payload, list):
            raise SerProviderApiError("ElParking zone list returned an unexpected shape")
        return payload

    def get_steps(self, access_token: str, zone_id: str, rate_id: str, vehicle_id: int) -> dict[str, Any]:
        """GET /v1/ser-steps/zone/<zoneId>/rate/<rateId>/vehicle/<vehicleId> — the mandatory pricing/checksum step."""
        payload = self._authenticated_get(
            access_token, f"/v1/ser-steps/zone/{zone_id}/rate/{rate_id}/vehicle/{vehicle_id}"
        )
        if not isinstance(payload, dict):
            raise SerProviderApiError("ElParking pricing steps returned an unexpected shape")
        return payload

    def create_ticket(self, access_token: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST /v1/ser-tickets — submit the final ticket-creation request."""
        headers = {"Content-Type": "application/json", **self._auth_headers()}

        try:
            with httpx.Client(timeout=_CREATE_TICKET_TIMEOUT_SECONDS) as client:
                response = client.post(
                    f"{self._base_url}/v1/ser-tickets",
                    json=body,
                    headers=headers,
                    auth=self._basic_auth(access_token),
                )
        except httpx.HTTPError as exc:
            raise SerProviderApiError(f"ElParking ticket creation request failed: {exc}") from exc

        if not response.is_success:
            raise SerProviderApiError(
                f"ElParking ticket creation returned unexpected status {response.status_code}: "
                f"{response.text[:200]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise SerProviderApiError(f"ElParking ticket creation returned a non-JSON response body: {exc}") from exc

        if not isinstance(payload, dict):
            raise SerProviderApiError("ElParking ticket creation returned an unexpected response shape")

        return payload
