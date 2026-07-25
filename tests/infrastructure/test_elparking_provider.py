"""
Unit tests for ElParkingSerTicketProvider.

login()/logout() are now thin delegations to ElParkingClient — HTTP-level
auth/header assertions live in test_elparking_client.py. This file exercises
create_ticket()'s full resolution + submission flow against a fake
ElParkingClient, fake SerZoneRepository/CityRepository, and a fake
zone-mapping repository — no real network or database access.
"""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import pytest
from shapely.geometry import Point

from mobility_manager.domain.entities.city import City
from mobility_manager.domain.entities.ser_zone import SerZone
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.exceptions import (
    SerProviderApiError,
    SerProviderVehicleNotFoundError,
    SerZoneNotFoundError,
)
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking import (
    provider as provider_module,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.provider import (
    ElParkingSerTicketProvider,
)
from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
    ElParkingZoneMapping,
)

_BASE_URL = "https://elparking.example.test"
_SQUARE_POLYGON_A = "POLYGON((-3.70 40.40, -3.699 40.40, -3.699 40.401, -3.70 40.401, -3.70 40.40))"


@pytest.fixture(autouse=True)
def _elparking_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELPARKING_API_BASE_URL", _BASE_URL)


def _make_vehicle(license_plate: str | None = "1234ABC") -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=Brand.GENERIC,
        display_name="Test Car",
        vin=None,
        license_plate=license_plate,
        created_at=datetime.now(UTC),
        user_id=uuid4(),
    )


def _make_ser_zone(city_code: str = "madrid", zone_number: str = "084", zone_type: str = "Azul") -> SerZone:
    return SerZone(
        city_code=city_code,
        zone_number=zone_number,
        zone_type=zone_type,
        district="Chamartín",
        spot_count=-1,
        geometry=Point(0, 0),  # not used — find_containing() is faked directly below
    )


class FakeElParkingClient:
    """Stands in for ElParkingClient — no real HTTP, every call is a canned/asserted response."""

    def __init__(self, base_url: str, app_version: str) -> None:
        self.base_url = base_url
        self.app_version = app_version
        self.login_calls: list[SerProviderCredentials] = []
        self.logout_calls: list[str] = []
        self.list_vehicles_return: list[dict[str, Any]] = []
        self.list_towns_return: list[dict[str, Any]] = []
        self.list_zones_return: list[dict[str, Any]] = []
        self.list_zones_calls: list[tuple[str, str]] = []
        self.get_steps_return: dict[str, Any] = {"steps": []}
        self.create_ticket_return: dict[str, Any] = {}
        self.create_ticket_calls: list[dict[str, Any]] = []

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        self.login_calls.append(credentials)
        return SerProviderSession(data={"access_token": "fake-token", "device_session_id": 1})

    def logout(self, access_token: str) -> None:
        self.logout_calls.append(access_token)

    def list_vehicles(self, access_token: str) -> list[dict[str, Any]]:
        return self.list_vehicles_return

    def list_towns(self, access_token: str) -> list[dict[str, Any]]:
        return self.list_towns_return

    def list_zones(self, access_token: str, town_id: str) -> list[dict[str, Any]]:
        self.list_zones_calls.append((access_token, town_id))
        return self.list_zones_return

    def get_steps(self, access_token: str, zone_id: str, rate_id: str, vehicle_id: int) -> dict[str, Any]:
        return self.get_steps_return

    def create_ticket(self, access_token: str, body: dict[str, Any]) -> dict[str, Any]:
        self.create_ticket_calls.append(body)
        return self.create_ticket_return


class FakeSerZoneRepo:
    def __init__(self, zone: SerZone | None) -> None:
        self._zone = zone

    def find_containing(self, location: GeoLocation) -> SerZone | None:
        return self._zone


class FakeCityRepo:
    def __init__(self, cities: list[City]) -> None:
        self._cities = cities

    def list_all(self) -> list[City]:
        return self._cities


class FakeZoneMappingRepo:
    def __init__(self, mapping: ElParkingZoneMapping | None = None) -> None:
        self._mapping = mapping
        self.saved: list[tuple[str, str, ElParkingZoneMapping]] = []

    def get(self, city_code: str, provider: str) -> ElParkingZoneMapping | None:
        return self._mapping

    def save(self, city_code: str, provider: str, mapping: ElParkingZoneMapping) -> None:
        self.saved.append((city_code, provider, mapping))
        self._mapping = mapping


def _make_provider(
    monkeypatch: pytest.MonkeyPatch,
    ser_zone_repo: Any = None,
    city_repo: Any = None,
    zone_mapping_repo: Any = None,
) -> tuple[ElParkingSerTicketProvider, FakeElParkingClient]:
    holder: dict[str, FakeElParkingClient] = {}

    def _fake_client_cls(base_url: str, app_version: str) -> FakeElParkingClient:
        client = FakeElParkingClient(base_url, app_version)
        holder["client"] = client
        return client

    monkeypatch.setattr(provider_module, "ElParkingClient", _fake_client_cls)

    provider = ElParkingSerTicketProvider(
        ser_zone_repo=ser_zone_repo if ser_zone_repo is not None else FakeSerZoneRepo(None),
        city_repo=city_repo if city_repo is not None else FakeCityRepo([]),
        zone_mapping_repo=zone_mapping_repo if zone_mapping_repo is not None else FakeZoneMappingRepo(),
    )
    return provider, holder["client"]


def test_login_delegates_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, client = _make_provider(monkeypatch)
    credentials = SerProviderCredentials(data={"email": "alice@example.com", "password": "s3cr3t"})

    session = provider.login(credentials)

    assert client.login_calls == [credentials]
    assert session.data == {"access_token": "fake-token", "device_session_id": 1}


def test_logout_delegates_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    provider, client = _make_provider(monkeypatch)
    session = SerProviderSession(data={"access_token": "fake-token"})

    provider.logout(session)

    assert client.logout_calls == ["fake-token"]


def _fresh_mapping(zones: list[dict[str, Any]]) -> ElParkingZoneMapping:
    from mobility_manager.infrastructure.ser_ticket_providers.elparking.zone_mapping import (
        ElParkingRate,
        ElParkingZone,
    )

    return ElParkingZoneMapping(
        id_ser_town="town-1",
        zones=[
            ElParkingZone(
                id=z["id"],
                name=z["name"],
                polygon_wkt=z["polygon_wkt"],
                rates=[ElParkingRate(id=r["id"], name=r["name"]) for r in z.get("rates", [])],
            )
            for z in zones
        ],
        fetched_at=datetime.now(UTC),
    )


def test_create_ticket_full_flow_resolves_and_submits(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle(license_plate="1234ABC")
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": ("POLYGON((-3.70 40.40, -3.699 40.40, -3.699 40.401, -3.70 40.401, -3.70 40.40))"),
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 42, "number_plate": "1234ABC"}]
    client.get_steps_return = {
        "steps": [{"minute": 60, "fare_qty": 2.5}],
        "security_checksum": "abc123",
    }
    client.create_ticket_return = {
        "id": "ticket-99",
        "total_qty": {"amount": 2.5},
        "end_date": "2026-07-23T14:00:00+00:00",
    }

    session = SerProviderSession(data={"access_token": "fake-token"})
    ticket = provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == [
        {
            "id_vehicle": 42,
            "id_ser_zone": "zone-84",
            "id_ser_rate": "rate-azul",
            "type": "TYPE_NORMAL",
            "start_date": client.create_ticket_calls[0]["start_date"],
            "duration_minutes": 60,
            "latitude": location.lat,
            "longitude": location.lng,
            "fare_qty": 2.5,
            # The entire GET /v1/ser-steps response, forwarded verbatim — see
            # design.md and _build_ticket_request_body's docstring.
            "step_request": client.get_steps_return,
        }
    ]
    assert ticket.provider == "elparking"
    assert ticket.vehicle_id == vehicle.id
    assert ticket.user_id == vehicle.user_id
    assert ticket.duration_minutes == 60
    assert ticket.cost == 2.5
    assert ticket.end_date == datetime.fromisoformat("2026-07-23T14:00:00+00:00")
    assert ticket.provider_reference == "ticket-99"


def test_create_ticket_vehicle_not_found_raises_without_further_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle(license_plate="9999ZZZ")
    provider, client = _make_provider(monkeypatch)
    client.list_vehicles_return = [{"id": 1, "number_plate": "1234ABC"}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderVehicleNotFoundError):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=GeoLocation(lat=40.0, lng=-3.0))

    assert client.list_zones_calls == []
    assert client.create_ticket_calls == []


def test_create_ticket_no_containing_ser_zone_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    provider, client = _make_provider(monkeypatch, ser_zone_repo=FakeSerZoneRepo(None))
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerZoneNotFoundError):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=GeoLocation(lat=40.0, lng=-3.0))

    assert client.create_ticket_calls == []


def test_create_ticket_disambiguates_duplicate_zone_number_by_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two cached zones share zone_number '084' — the one containing `location` must win."""
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone(zone_number="084")
    # Location falls inside zone A's square, nowhere near zone B's square.
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-A",
                "name": "084 - ZONE A",
                "polygon_wkt": ("POLYGON((-3.70 40.40, -3.699 40.40, -3.699 40.401, -3.70 40.401, -3.70 40.40))"),
                "rates": [{"id": "rate-azul-a", "name": "Tarifa Azul"}],
            },
            {
                "id": "zone-B",
                "name": "084 - ZONE B",
                "polygon_wkt": ("POLYGON((-3.60 40.30, -3.599 40.30, -3.599 40.301, -3.60 40.301, -3.60 40.30))"),
                "rates": [{"id": "rate-azul-b", "name": "Tarifa Azul"}],
            },
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.get_steps_return = {"steps": [{"minute": 30, "fare_qty": 1.0}]}
    client.create_ticket_return = {
        "id": "ticket-1",
        "total_qty": {"amount": 1.0},
        "end_date": "2026-07-23T14:00:00+00:00",
    }

    session = SerProviderSession(data={"access_token": "fake-token"})
    provider.create_ticket(session, vehicle, duration_minutes=30, location=location)

    assert client.create_ticket_calls[0]["id_ser_zone"] == "zone-A"
    assert client.create_ticket_calls[0]["id_ser_rate"] == "rate-azul-a"


def test_create_ticket_cache_hit_skips_town_zone_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": "POLYGON((-3.70 40.40, -3.699 40.40, -3.699 40.401, -3.70 40.401, -3.70 40.40))",
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )
    zone_mapping_repo = FakeZoneMappingRepo(mapping)

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=zone_mapping_repo,
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.get_steps_return = {"steps": [{"minute": 30, "fare_qty": 1.0}]}
    client.create_ticket_return = {
        "id": "ticket-1",
        "total_qty": {"amount": 1.0},
        "end_date": "2026-07-23T14:00:00+00:00",
    }

    session = SerProviderSession(data={"access_token": "fake-token"})
    provider.create_ticket(session, vehicle, duration_minutes=30, location=location)

    assert client.list_zones_calls == []
    assert zone_mapping_repo.saved == []


def test_create_ticket_cache_miss_fetches_and_saves_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone(city_code="madrid")
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    zone_mapping_repo = FakeZoneMappingRepo(None)
    city_repo = FakeCityRepo([City(code="madrid", name="Madrid")])

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        city_repo=city_repo,
        zone_mapping_repo=zone_mapping_repo,
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.list_towns_return = [{"id": "town-1", "name": "Madrid"}]
    client.list_zones_return = [
        {
            "id": "zone-84",
            "name": "84 - PILAR",
            "polygon_wkt": "POLYGON((-3.70 40.40, -3.699 40.40, -3.699 40.401, -3.70 40.401, -3.70 40.40))",
            "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
        }
    ]
    client.get_steps_return = {"steps": [{"minute": 30, "fare_qty": 1.0}]}
    client.create_ticket_return = {
        "id": "ticket-1",
        "total_qty": {"amount": 1.0},
        "end_date": "2026-07-23T14:00:00+00:00",
    }

    session = SerProviderSession(data={"access_token": "fake-token"})
    provider.create_ticket(session, vehicle, duration_minutes=30, location=location)

    assert client.list_zones_calls == [("fake-token", "town-1")]
    assert len(zone_mapping_repo.saved) == 1
    saved_city_code, saved_provider, saved_mapping = zone_mapping_repo.saved[0]
    assert saved_city_code == "madrid"
    assert saved_provider == "elparking"
    assert saved_mapping.id_ser_town == "town-1"


def test_create_ticket_no_city_registered_raises_provider_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone(city_code="unknown-city")
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        city_repo=FakeCityRepo([]),
        zone_mapping_repo=FakeZoneMappingRepo(None),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="No city registered"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_no_elparking_town_match_raises_provider_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone(city_code="madrid")
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        city_repo=FakeCityRepo([City(code="madrid", name="Madrid")]),
        zone_mapping_repo=FakeZoneMappingRepo(None),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.list_towns_return = [{"id": "town-1", "name": "Barcelona"}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="No ElParking town found"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_no_matching_elparking_zone_raises_provider_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone(zone_number="999")
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="No ElParking zone found"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_no_license_plate_raises_vehicle_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle(license_plate=None)
    provider, client = _make_provider(monkeypatch)
    client.list_vehicles_return = [{"id": 1, "number_plate": "1234ABC"}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderVehicleNotFoundError):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=GeoLocation(lat=40.0, lng=-3.0))


def test_create_ticket_malformed_step_missing_fare_qty_raises_provider_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    # Matches duration, but missing "fare_qty" — malformed shape.
    client.get_steps_return = {"steps": [{"minute": 60}]}

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="unexpected shape"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_malformed_steps_response_raises_provider_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    # "steps" is not iterable — malformed shape.
    client.get_steps_return = {"steps": None}

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="unexpected shape"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_malformed_zones_response_raises_provider_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone(city_code="madrid")
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    zone_mapping_repo = FakeZoneMappingRepo(None)
    city_repo = FakeCityRepo([City(code="madrid", name="Madrid")])

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        city_repo=city_repo,
        zone_mapping_repo=zone_mapping_repo,
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.list_towns_return = [{"id": "town-1", "name": "Madrid"}]
    # Missing "polygon_wkt" — malformed shape.
    client.list_zones_return = [{"id": "zone-84", "name": "84 - PILAR"}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="unexpected shape"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_no_matching_rate_raises_provider_api_error(monkeypatch: pytest.MonkeyPatch) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone(zone_type="Verde")
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="No ElParking rate found"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_no_steps_offered_raises_provider_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty steps[] list (no pricing offered at all) still raises — there's no "nearest" of nothing."""
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.get_steps_return = {"steps": []}

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="No ElParking pricing step"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)

    assert client.create_ticket_calls == []


def test_create_ticket_uses_nearest_step_when_exact_duration_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ElParking's steps are irregular (e.g. every ~10-15 minutes) — an exact match is the exception."""
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.get_steps_return = {
        "steps": [
            {"minute": 16, "fare_qty": 0.05},
            {"minute": 30, "fare_qty": 0.10},
            {"minute": 47, "fare_qty": 0.20},
        ]
    }
    client.create_ticket_return = {
        "id": "ticket-1",
        "total_qty": {"amount": 0.10},
        "end_date": "2026-07-23T14:00:00+00:00",
    }

    session = SerProviderSession(data={"access_token": "fake-token"})
    # Requested 35 — closer to the 30-minute step (distance 5) than 47 (distance 12).
    provider.create_ticket(session, vehicle, duration_minutes=35, location=location)

    # fare_qty comes from the selected (nearest) step, proving 30-minute was picked.
    assert client.create_ticket_calls[0]["fare_qty"] == 0.10
    # step_request is always the whole steps_response, regardless of which step matched.
    assert client.create_ticket_calls[0]["step_request"] == client.get_steps_return


def test_create_ticket_nearest_step_breaks_ties_toward_earlier_entry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    # 30 and 40 are equidistant from the requested 35 — the earlier entry (30) wins.
    client.get_steps_return = {
        "steps": [
            {"minute": 30, "fare_qty": 0.10},
            {"minute": 40, "fare_qty": 0.15},
        ]
    }
    client.create_ticket_return = {
        "id": "ticket-1",
        "total_qty": {"amount": 0.10},
        "end_date": "2026-07-23T14:00:00+00:00",
    }

    session = SerProviderSession(data={"access_token": "fake-token"})
    provider.create_ticket(session, vehicle, duration_minutes=35, location=location)

    assert client.create_ticket_calls[0]["fare_qty"] == 0.10


def test_create_ticket_malformed_ticket_response_missing_total_qty_raises_provider_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.get_steps_return = {"steps": [{"minute": 60, "fare_qty": 1.0}]}
    # Missing "total_qty" entirely — malformed response shape.
    client.create_ticket_return = {"id": "ticket-1", "end_date": "2026-07-23T14:00:00+00:00"}

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="unexpected response body"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)


def test_create_ticket_malformed_ticket_response_missing_end_date_raises_provider_api_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vehicle = _make_vehicle()
    ser_zone = _make_ser_zone()
    location = GeoLocation(lat=40.4005, lng=-3.6995)

    mapping = _fresh_mapping(
        [
            {
                "id": "zone-84",
                "name": "84 - PILAR",
                "polygon_wkt": _SQUARE_POLYGON_A,
                "rates": [{"id": "rate-azul", "name": "Tarifa Azul"}],
            }
        ]
    )

    provider, client = _make_provider(
        monkeypatch,
        ser_zone_repo=FakeSerZoneRepo(ser_zone),
        zone_mapping_repo=FakeZoneMappingRepo(mapping),
    )
    client.list_vehicles_return = [{"id": 1, "number_plate": vehicle.license_plate}]
    client.get_steps_return = {"steps": [{"minute": 60, "fare_qty": 1.0}]}
    # Missing "end_date" entirely — malformed response shape.
    client.create_ticket_return = {"id": "ticket-1", "total_qty": {"amount": 1.0}}

    session = SerProviderSession(data={"access_token": "fake-token"})

    with pytest.raises(SerProviderApiError, match="unexpected response body"):
        provider.create_ticket(session, vehicle, duration_minutes=60, location=location)
