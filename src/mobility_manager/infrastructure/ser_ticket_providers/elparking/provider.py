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

# Only TYPE_NORMAL is supported in this change — see design.md Non-Goals
# ("No support for TYPE_EXTENDED"). ElParking's documented ticket types
# distinguish a brand-new ticket (TYPE_NORMAL) from extending an existing
# active one (TYPE_EXTENDED); this integration only ever creates new tickets.
_TICKET_TYPE_NORMAL = "TYPE_NORMAL"


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
        id_vehicle = self._match_vehicle(elparking_vehicles, vehicle.license_plate)
        if id_vehicle is None:
            raise SerProviderVehicleNotFoundError(
                f"No ElParking vehicle found matching license plate {vehicle.license_plate!r}"
            )

        ser_zone = self._ser_zone_repo.find_containing(location)
        if ser_zone is None:
            raise SerZoneNotFoundError(f"No SER zone found containing location {location!r}")

        mapping = self._get_or_refresh_mapping(access_token, ser_zone.city_code)

        elparking_zone = resolve_zone(ser_zone.zone_number, location, mapping.zones)
        if elparking_zone is None:
            raise SerProviderApiError(
                f"No ElParking zone found matching zone_number {ser_zone.zone_number!r} "
                f"in town {mapping.id_ser_town!r}"
            )

        elparking_rate = resolve_rate(ser_zone.zone_type, elparking_zone.rates)
        if elparking_rate is None:
            raise SerProviderApiError(
                f"No ElParking rate found matching zone_type {ser_zone.zone_type!r} "
                f"for zone {elparking_zone.id!r}"
            )

        steps_response = self._client.get_steps(access_token, elparking_zone.id, elparking_rate.id, id_vehicle)
        step = self._select_step(steps_response, duration_minutes)
        if step is None:
            raise SerProviderApiError(f"No ElParking pricing step found for duration_minutes={duration_minutes}")

        body = self._build_ticket_request_body(
            id_vehicle=id_vehicle,
            elparking_zone_id=elparking_zone.id,
            elparking_rate_id=elparking_rate.id,
            duration_minutes=duration_minutes,
            location=location,
            step=step,
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
            created_at=datetime.now(UTC),
        )

    def _build_ticket_request_body(
        self,
        id_vehicle: int,
        elparking_zone_id: str,
        elparking_rate_id: str,
        duration_minutes: int,
        location: GeoLocation,
        step: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Build the POST /v1/ser-tickets request body.

        ASSUMPTION — UNVERIFIED AGAINST THE LIVE API (see tasks.md 10.3):
        the exact body field names aren't confirmed by any sampled response;
        these follow the snake_case convention already observed in
        ser-towns.json/ser-zones.json and the fields design.md explicitly
        calls out (id_vehicle, id_ser_zone, id_ser_rate, fare_qty,
        step_request). Update this method alone if real-API testing shows
        different keys.

        Raises:
            SerProviderApiError: `step` is missing an expected key (a
                malformed/unexpected-shape `get_steps()` response).
        """
        try:
            fare_qty = step["fare_qty"]
            # Forwarded verbatim — never constructed or altered — the server
            # re-validates its own security_checksum embedded in this value
            # (see design.md Risk: Step 5's freshness window).
            step_request = step["step_request"]
        except (KeyError, TypeError, IndexError) as exc:
            raise SerProviderApiError(f"ElParking pricing step has an unexpected shape: {exc}") from exc

        return {
            "id_vehicle": id_vehicle,
            "id_ser_zone": elparking_zone_id,
            "id_ser_rate": elparking_rate_id,
            "type": _TICKET_TYPE_NORMAL,
            "start_date": datetime.now(UTC).isoformat(),
            "duration_minutes": duration_minutes,
            "latitude": location.lat,
            "longitude": location.lng,
            "fare_qty": fare_qty,
            "step_request": step_request,
        }

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

    def _match_vehicle(self, elparking_vehicles: list[dict[str, Any]], license_plate: str | None) -> int | None:
        """
        Match `license_plate` against ElParking's vehicle list; return its `id`, or None.

        Confirmed against a real GET /v1/users/me/vehicles response: the
        plate field is "number_plate", not "license_plate" — the latter was
        an unverified assumption that never matched, so ticket creation
        always raised SerProviderVehicleNotFoundError. "id" was correct.
        """
        if license_plate is None:
            return None
        for v in elparking_vehicles:
            if v.get("number_plate") == license_plate:
                return v.get("id")
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
