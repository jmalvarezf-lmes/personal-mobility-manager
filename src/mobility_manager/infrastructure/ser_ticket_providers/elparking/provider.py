"""
Infrastructure: ElParkingSerTicketProvider.

Thin orchestrator over ElParkingClient: login()/logout() simply delegate to
the client. create_ticket() resolves the vehicle's ElParking id_vehicle,
the SER zone containing the given location (via our own SerZoneRepository —
ElParking's own polygons are only consulted to disambiguate a duplicate
zone_number within a town), the ElParking town/zone/rate IDs (via the
zone-mapping cache, refreshed lazily on a miss/stale entry), the mandatory
pricing/checksum step, and finally submits the ticket.

See client.py for the HTTP mechanics and design.md decisions 1-6 for the
full resolution algorithm.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from mobility_manager.config import get_elparking_app_version, get_elparking_base_url
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderVehicleNotFoundError,
    SerZoneNotFoundError,
)
from mobility_manager.domain.ports.city_repository import CityRepository
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.ports.ser_zone_repository import SerZoneRepository
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.client import (
    ElParkingClient,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
    ElParkingRate,
    ElParkingZone,
    ElParkingZoneMapping,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping_repository import (
    PostgresElParkingZoneMappingRepository,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_resolver import (
    resolve_rate,
    resolve_town_id,
    resolve_zone,
)

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "elparking"


class ElParkingSerTicketProvider(SerTicketProviderPort):
    """SER ticket provider backed by ElParking's REST API."""

    def __init__(
        self,
        ser_zone_repo: SerZoneRepository,
        city_repo: CityRepository,
        zone_mapping_repo: PostgresElParkingZoneMappingRepository,
    ) -> None:
        # Fails fast if ELPARKING_API_BASE_URL is unset — in practice this is
        # already validated by SerTicketProviderRegistry before instantiation,
        # but resolving it here keeps the provider self-contained and safe to
        # construct directly (e.g. in tests).
        self._base_url = get_elparking_base_url()
        self._client = ElParkingClient(base_url=self._base_url, app_version=get_elparking_app_version())
        self._ser_zone_repo = ser_zone_repo
        self._city_repo = city_repo
        self._zone_mapping_repo = zone_mapping_repo

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        """Authenticate with ElParking and return a minimal session — delegates to ElParkingClient."""
        return self._client.login(credentials)

    def logout(self, session: SerProviderSession) -> None:
        """
        Invalidate the given session on ElParking's side — delegates to ElParkingClient.

        Raises:
            SerProviderApiError: Network error, timeout, or a non-2xx response.
        """
        access_token = session.data["access_token"]
        self._client.logout(access_token)

    def create_ticket(
        self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int, location: GeoLocation
    ) -> ParkingTicket:
        """
        Create a parking ticket for `vehicle` at `location` using `session`.

        Raises:
            SerProviderVehicleNotFoundError: `vehicle.license_plate` doesn't
                match any vehicle in the authenticated user's ElParking
                vehicle list.
            SerZoneNotFoundError: `location` doesn't fall inside any of our
                own stored SER zones.
            SerProviderApiError: Any other provider-side or resolution
                failure (no ElParking town/zone/rate match, no pricing step
                for the requested duration, or a raw HTTP/response failure).
        """
        access_token = session.data["access_token"]

        elparking_vehicles = self._client.list_vehicles(access_token)
        matched_vehicle = self._match_vehicle(elparking_vehicles, vehicle.license_plate)
        if matched_vehicle is None:
            raise SerProviderVehicleNotFoundError(
                f"No ElParking vehicle found matching license plate {vehicle.license_plate!r}"
            )
        try:
            id_vehicle = matched_vehicle["id"]
            id_wallet = matched_vehicle["wallet"]["id"]
        except (KeyError, TypeError) as exc:
            raise SerProviderApiError(f"ElParking vehicle entry has an unexpected shape: {exc}") from exc

        ser_zone = self._ser_zone_repo.find_containing(location)
        if ser_zone is None:
            raise SerZoneNotFoundError(f"No SER zone found containing location {location!r}")

        mapping = self._get_or_refresh_mapping(access_token, ser_zone.city_code)

        elparking_zone = resolve_zone(ser_zone.zone_number, location, mapping.zones)
        if elparking_zone is None:
            raise SerProviderApiError(
                f"No ElParking zone found matching zone_number {ser_zone.zone_number!r} in town {mapping.id_ser_town!r}"
            )

        elparking_rate = resolve_rate(ser_zone.zone_type, elparking_zone.rates)
        if elparking_rate is None:
            raise SerProviderApiError(
                f"No ElParking rate found matching zone_type {ser_zone.zone_type!r} for zone {elparking_zone.id!r}"
            )

        steps_response = self._client.get_steps(access_token, elparking_zone.id, elparking_rate.id, id_vehicle)
        step = self._select_step(steps_response, duration_minutes)
        if step is None:
            raise SerProviderApiError(f"No ElParking pricing step found for duration_minutes={duration_minutes}")

        body, start_date = self._build_ticket_request_body(
            id_vehicle=id_vehicle,
            id_wallet=id_wallet,
            elparking_zone_id=elparking_zone.id,
            elparking_rate_id=elparking_rate.id,
            location=location,
            step=step,
            steps_response=steps_response,
        )

        response = self._client.create_ticket(access_token, body)

        cost, end_date, provider_reference = self._parse_ticket_response(response)

        return ParkingTicket(
            id=uuid4(),
            vehicle_id=vehicle.id,
            user_id=vehicle.user_id,
            provider=_PROVIDER_NAME,
            duration_minutes=duration_minutes,
            provider_reference=provider_reference,
            cost=cost,
            end_date=end_date,
            start_date=start_date,
            created_at=datetime.now(UTC),
            city_code=ser_zone.city_code,
            zone_number=ser_zone.zone_number,
        )

    def _build_ticket_request_body(
        self,
        id_vehicle: int,
        id_wallet: int,
        elparking_zone_id: str,
        elparking_rate_id: str,
        location: GeoLocation,
        step: dict[str, Any],
        steps_response: dict[str, Any],
    ) -> tuple[dict[str, Any], datetime]:
        """
        Build the POST /v1/ser-tickets request body, plus the parsed start_date.

        Returns the request body together with the whole steps_response's own
        top-level "start_time" parsed into a datetime — the same value sent as
        the request's "start_date" — so the caller can persist it as the
        ParkingTicket's real start date instead of relying on created_at
        (wall-clock time of our own record, not the parking session).
        "start_time" lives at the top level of the GET /v1/ser-steps response,
        not inside each per-minute `step` entry — each step only carries its
        own "time" (start_time + minute*60, i.e. that step's own end time, not
        a start).

        "step_request" is the *entire* GET /v1/ser-steps response body
        (`steps_response`), forwarded verbatim — design.md is explicit that
        the server re-validates the `security_checksum` embedded in that
        whole response and rejects stale requests, so it must be echoed back
        whole, not reconstructed from a subset of fields. The former
        implementation looked for a "step_request" key *inside* the selected
        per-minute `step` entry — that key never existed there (confirmed by
        a real response sample), which raised "unexpected shape" for every
        ticket creation. "fare_qty" does come from the selected `step`.

        "type" and the duration field name were also wrong against the live
        API (per direct user correction): "type" is mandatory but must be
        the integer 0 for a normal ticket, not the string "TYPE_NORMAL" this
        used to send; and the duration field is "stay_duration".

        "stay_duration" must be the selected step's own "minute" value, not
        the originally requested duration. ElParking's steps are irregular,
        so `_select_step` picks the nearest available step rather than an
        exact match — echoing back the originally requested duration while
        paying the nearest step's `fare_qty` is an inconsistent request that
        ElParking's API can reject.

        Also per direct user correction: "start_date" must be a Unix
        timestamp in whole seconds, not an ISO 8601 string — "user_latitude"/
        "user_longitude" must be sent alongside "latitude"/"longitude" with
        the same values — and "id_wallet" (the matched vehicle's nested
        `wallet.id` from GET /v1/users/me/vehicles) must be included.

        "start_date" is `steps_response`'s own top-level "start_time" — not
        wall-clock "now". The whole pricing response (fare/duration options)
        was computed for that specific start time, so echoing back anything
        else would send an inconsistent request, the same class of bug
        "stay_duration" already had to avoid above.

        Raises:
            SerProviderApiError: `step` is missing the "fare_qty" or "minute"
                key, or `steps_response` is missing the top-level "start_time"
                key (a malformed/unexpected-shape `get_steps()` response).
        """
        try:
            fare_qty = step["fare_qty"]
            stay_duration = step["minute"]
        except (KeyError, TypeError, IndexError) as exc:
            raise SerProviderApiError(f"ElParking pricing step has an unexpected shape: {exc}") from exc

        try:
            start_time = steps_response["start_time"]
        except (KeyError, TypeError) as exc:
            raise SerProviderApiError(f"ElParking steps response has an unexpected shape: {exc}") from exc

        start_date = datetime.fromtimestamp(int(start_time), tz=UTC)

        body = {
            "id_vehicle": id_vehicle,
            "id_wallet": id_wallet,
            "id_ser_zone": elparking_zone_id,
            "id_ser_rate": elparking_rate_id,
            # Mandatory — a normal (non-extended) ticket is integer 0, not the
            # string "TYPE_NORMAL" this used to send (per user correction
            # against the live API).
            "type": 0,
            "start_date": start_time,
            "stay_duration": stay_duration,
            "latitude": location.lat,
            "longitude": location.lng,
            "user_latitude": location.lat,
            "user_longitude": location.lng,
            "fare_qty": fare_qty,
            "step_request": steps_response,
        }
        return body, start_date

    def _parse_ticket_response(self, response: dict[str, Any]) -> tuple[float, datetime, str | None]:
        """
        Parse `POST /v1/ser-tickets`'s response into (cost, end_date, provider_reference).

        "total_qty" is a nested money object (`{"amount": float, "amountInMinorUnits":
        int, "currency": str, ...}`), not a bare number — confirmed by a real
        GET /v1/ser-steps response, where every *_qty field (fare_qty,
        commission_qty, total_qty, ...) uses this same shape. The
        ticket-creation response isn't itself sampled yet, but this money-object
        convention is consistent everywhere else in ElParking's API (including
        the vehicle wallet's `qty` field), so it's applied here too.
        "end_date"/"id" remain unverified assumptions (see design.md 10.3).

        Raises:
            SerProviderApiError: The response is missing/malformed for
                `total_qty` or `end_date`.
        """
        try:
            cost = float(response["total_qty"]["amount"])
            end_date = datetime.fromisoformat(response["end_date"])
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise SerProviderApiError(f"ElParking ticket creation returned an unexpected response body: {exc}") from exc

        provider_reference = str(response.get("id")) if response.get("id") is not None else None
        return cost, end_date, provider_reference

    def _match_vehicle(
        self, elparking_vehicles: list[dict[str, Any]], license_plate: str | None
    ) -> dict[str, Any] | None:
        """
        Match `license_plate` against ElParking's vehicle list; return the matched entry, or None.

        Confirmed against a real GET /v1/users/me/vehicles response: the
        plate field is "number_plate", not "license_plate" — the latter was
        an unverified assumption that never matched, so ticket creation
        always raised SerProviderVehicleNotFoundError. "id" was correct.
        Returns the whole matched dict (not just its "id") because the
        caller also needs its nested "wallet"."id" for id_wallet.
        """
        if license_plate is None:
            return None
        for v in elparking_vehicles:
            if v.get("number_plate") == license_plate:
                return v
        return None

    def _select_step(self, steps_response: dict[str, Any], duration_minutes: int) -> dict[str, Any] | None:
        """
        Select the steps[] entry closest to duration_minutes.

        Confirmed against a real GET /v1/ser-steps response: each entry's
        duration field is "minute" — "stay_duration" (the former assumption)
        doesn't exist anywhere in the response, so it never matched and every
        ticket creation failed with "No ElParking pricing step found".
        ElParking's steps are irregular (e.g. 16, 30, 39, 47, ... minutes),
        not one per minute, so an exact match is the exception rather than
        the rule: the entry whose "minute" is numerically closest to
        duration_minutes is used instead (ties keep the earlier entry).

        Raises:
            SerProviderApiError: `steps_response` has an unexpected shape
                (not a dict, `steps` not iterable, or an entry not a dict).
        """
        try:
            steps: list[dict[str, Any]] = steps_response.get("steps", [])
            return min(steps, key=lambda step: abs(step["minute"] - duration_minutes))
        except ValueError:
            # min() on an empty steps list — genuinely no pricing step offered.
            return None
        except (KeyError, TypeError, IndexError) as exc:
            raise SerProviderApiError(f"ElParking steps response has an unexpected shape: {exc}") from exc

    def _get_or_refresh_mapping(self, access_token: str, city_code: str) -> ElParkingZoneMapping:
        """
        Return the cached (city_code, elparking) mapping, refreshing it on a miss/stale entry.

        Raises:
            SerProviderApiError: No city registered for `city_code`, no
                ElParking town match, or `list_zones()` returned an
                unexpected shape (missing/malformed zone or rate fields).
        """
        mapping = self._zone_mapping_repo.get(city_code, _PROVIDER_NAME)
        if mapping is not None:
            return mapping

        city = next((c for c in self._city_repo.list_all() if c.code == city_code), None)
        if city is None:
            raise SerProviderApiError(f"No city registered for city_code {city_code!r}")

        towns = self._client.list_towns(access_token)
        id_ser_town = resolve_town_id(city.name, towns)
        if id_ser_town is None:
            raise SerProviderApiError(f"No ElParking town found matching city {city.name!r}")

        raw_zones = self._client.list_zones(access_token, id_ser_town)
        try:
            zones = [
                ElParkingZone(
                    id=z["id"],
                    name=z["name"],
                    polygon_wkt=z["polygon_wkt"],
                    rates=[ElParkingRate(id=r["id"], name=r["name"]) for r in z.get("rates", [])],
                )
                for z in raw_zones
            ]
        except (KeyError, TypeError, IndexError) as exc:
            raise SerProviderApiError(f"ElParking zones response has an unexpected shape: {exc}") from exc

        mapping = ElParkingZoneMapping(id_ser_town=id_ser_town, zones=zones, fetched_at=datetime.now(UTC))
        self._zone_mapping_repo.save(city_code, _PROVIDER_NAME, mapping)
        return mapping
