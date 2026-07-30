"""
Unit tests for CreateSerTicket use case.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from mobility_manager.application.use_cases.create_ser_ticket import CreateSerTicket
from mobility_manager.domain.entities.parking_ticket import ParkingTicket
from mobility_manager.domain.entities.vehicle import Vehicle
from mobility_manager.domain.entities.vehicle_location import VehicleLocation
from mobility_manager.domain.events.vehicle_not_present_in_ser_ticket_provider import (
    VehicleNotPresentInSerTicketProvider,
)
from mobility_manager.domain.exceptions import (
    SerProviderSessionNotFoundError,
    SerProviderVehicleNotFoundError,
    SerTicketPersistenceError,
    SerTicketProviderNotFoundError,
    VehicleNotFoundError,
)
from mobility_manager.domain.ports.ser_ticket_provider import SerTicketProviderPort
from mobility_manager.domain.value_objects.brand import Brand
from mobility_manager.domain.value_objects.location import GeoLocation
from mobility_manager.domain.value_objects.ser_provider_credentials import (
    SerProviderCredentials,
)
from mobility_manager.domain.value_objects.ser_provider_session import (
    SerProviderSession,
)

_OWNER = uuid4()
_OTHER_USER = uuid4()


def _make_vehicle(user_id: UUID) -> Vehicle:
    return Vehicle(
        id=uuid4(),
        brand=Brand.GENERIC,
        display_name="Test Car",
        vin=None,
        license_plate=None,
        created_at=datetime.now(UTC),
        user_id=user_id,
    )


class FakeSerTicketProvider(SerTicketProviderPort):
    def __init__(self, raise_vehicle_not_found: bool = False) -> None:
        self.create_ticket_calls: list[tuple[SerProviderSession, Vehicle, int, GeoLocation]] = []
        self._raise_vehicle_not_found = raise_vehicle_not_found

    def login(self, credentials: SerProviderCredentials) -> SerProviderSession:
        raise NotImplementedError("Not exercised by CreateSerTicket tests")

    def create_ticket(
        self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int, location: GeoLocation
    ) -> ParkingTicket:
        self.create_ticket_calls.append((session, vehicle, duration_minutes, location))
        if self._raise_vehicle_not_found:
            raise SerProviderVehicleNotFoundError("no matching vehicle on provider's side")
        return ParkingTicket(
            id=uuid4(),
            vehicle_id=vehicle.id,
            user_id=vehicle.user_id,
            provider="madrid_ser_app",
            duration_minutes=duration_minutes,
            provider_reference="REF-123",
            cost=1.5,
            end_date=datetime.now(UTC),
            created_at=datetime.now(UTC),
            city_code="madrid",
            zone_number="163",
        )

    def logout(self, session: SerProviderSession) -> None:
        raise NotImplementedError("Not exercised by CreateSerTicket tests")


class InMemoryVehicleRepo:
    def __init__(self) -> None:
        self.vehicles: dict[UUID, Vehicle] = {}

    def add(self, vehicle: Vehicle) -> None:
        self.vehicles[vehicle.id] = vehicle

    def find_by_id(self, vehicle_id: UUID) -> Vehicle | None:
        return self.vehicles.get(vehicle_id)


class InMemoryUserSerProviderConfigRepo:
    def __init__(self) -> None:
        self.sessions: dict[tuple[UUID, str], SerProviderSession] = {}

    def add(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        self.sessions[(user_id, provider)] = session

    def find(self, user_id: UUID, provider: str) -> SerProviderSession | None:
        return self.sessions.get((user_id, provider))

    def save(self, user_id: UUID, provider: str, session: SerProviderSession) -> None:
        self.sessions[(user_id, provider)] = session


class InMemoryParkingTicketRepo:
    def __init__(self, raise_on_save: bool = False, fail_first_n_saves: int = 0) -> None:
        self.saved: list[ParkingTicket] = []
        self.save_calls = 0
        self._raise_on_save = raise_on_save
        self._fail_first_n_saves = fail_first_n_saves

    def save(self, ticket: ParkingTicket) -> None:
        self.save_calls += 1
        if self._raise_on_save:
            raise RuntimeError("db is down")
        if self.save_calls <= self._fail_first_n_saves:
            raise RuntimeError("transient db blip")
        self.saved.append(ticket)


class FakeEventPublisher:
    def __init__(self) -> None:
        self.published: list[object] = []

    def publish(self, event: object) -> None:
        self.published.append(event)


class FakeGetLatestVehicleLocation:
    def __init__(self, location: VehicleLocation | None = None) -> None:
        self._location = location
        self.calls: list[UUID] = []

    def execute(self, vehicle_id: UUID) -> VehicleLocation:
        self.calls.append(vehicle_id)
        if self._location is None:
            from mobility_manager.domain.exceptions import VehicleLocationNotFoundError

            raise VehicleLocationNotFoundError(f"No location history for {vehicle_id}")
        return self._location


def _make_use_case(provider: SerTicketProviderPort | None = None, latest_location: VehicleLocation | None = None):
    vehicle_repo = InMemoryVehicleRepo()
    config_repo = InMemoryUserSerProviderConfigRepo()
    ticket_repo = InMemoryParkingTicketRepo()
    provider = provider or FakeSerTicketProvider()
    event_publisher = FakeEventPublisher()
    get_latest_vehicle_location = FakeGetLatestVehicleLocation(latest_location)
    uc = CreateSerTicket(
        vehicle_repo=vehicle_repo,
        config_repo=config_repo,
        ticket_repo=ticket_repo,
        providers={"madrid_ser_app": provider},
        event_publisher=event_publisher,
        get_latest_vehicle_location=get_latest_vehicle_location,
    )
    return uc, vehicle_repo, config_repo, ticket_repo, provider, event_publisher, get_latest_vehicle_location


def test_successful_ticket_creation_with_explicit_location_persists_and_returns_ticket() -> None:
    uc, vehicle_repo, config_repo, ticket_repo, provider, _event_publisher, get_latest = _make_use_case()
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    session = SerProviderSession(data={"token": "abc"})
    config_repo.add(_OWNER, "madrid_ser_app", session)
    location = GeoLocation(lat=40.4, lng=-3.7)

    result = uc.execute(
        user_id=_OWNER, vehicle_id=vehicle.id, provider="madrid_ser_app", duration_minutes=90, location=location
    )

    assert provider.create_ticket_calls == [(session, vehicle, 90, location)]
    assert ticket_repo.saved == [result]
    assert result.vehicle_id == vehicle.id
    assert result.duration_minutes == 90
    assert get_latest.calls == []
    assert result.latitude == location.lat
    assert result.longitude == location.lng
    assert result.auto_created is False


def test_successful_ticket_creation_falls_back_to_latest_known_location() -> None:
    latest_location = VehicleLocation(
        id=uuid4(),
        vehicle_id=uuid4(),
        latitude=40.41,
        longitude=-3.68,
        recorded_at=datetime.now(UTC),
        received_at=datetime.now(UTC),
        source="pull",
    )
    uc, vehicle_repo, config_repo, ticket_repo, provider, _event_publisher, get_latest = _make_use_case(
        latest_location=latest_location
    )
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    session = SerProviderSession(data={"token": "abc"})
    config_repo.add(_OWNER, "madrid_ser_app", session)

    result = uc.execute(user_id=_OWNER, vehicle_id=vehicle.id, provider="madrid_ser_app", duration_minutes=90)

    assert get_latest.calls == [vehicle.id]
    called_location = provider.create_ticket_calls[0][3]
    assert called_location.lat == latest_location.latitude
    assert called_location.lng == latest_location.longitude
    assert result.latitude == latest_location.latitude
    assert result.longitude == latest_location.longitude


def test_explicit_auto_created_true_is_persisted_unchanged() -> None:
    uc, vehicle_repo, config_repo, ticket_repo, provider, _event_publisher, _get_latest = _make_use_case()
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    session = SerProviderSession(data={"token": "abc"})
    config_repo.add(_OWNER, "madrid_ser_app", session)
    location = GeoLocation(lat=40.4, lng=-3.7)

    result = uc.execute(
        user_id=_OWNER,
        vehicle_id=vehicle.id,
        provider="madrid_ser_app",
        duration_minutes=90,
        location=location,
        auto_created=True,
    )

    assert result.auto_created is True
    assert ticket_repo.saved == [result]


def test_vehicle_not_owned_by_user_raises_vehicle_not_found() -> None:
    uc, vehicle_repo, config_repo, ticket_repo, provider, _event_publisher, _get_latest = _make_use_case()
    vehicle = _make_vehicle(_OTHER_USER)
    vehicle_repo.add(vehicle)
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={}))

    with pytest.raises(VehicleNotFoundError):
        uc.execute(
            user_id=_OWNER,
            vehicle_id=vehicle.id,
            provider="madrid_ser_app",
            duration_minutes=60,
            location=GeoLocation(lat=40.0, lng=-3.0),
        )

    assert provider.create_ticket_calls == []
    assert ticket_repo.saved == []


def test_unknown_vehicle_raises_vehicle_not_found() -> None:
    uc, _vehicle_repo, config_repo, _ticket_repo, provider, _event_publisher, _get_latest = _make_use_case()
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={}))

    with pytest.raises(VehicleNotFoundError):
        uc.execute(
            user_id=_OWNER,
            vehicle_id=uuid4(),
            provider="madrid_ser_app",
            duration_minutes=60,
            location=GeoLocation(lat=40.0, lng=-3.0),
        )

    assert provider.create_ticket_calls == []


def test_missing_session_raises_session_not_found() -> None:
    uc, vehicle_repo, _config_repo, _ticket_repo, provider, _event_publisher, _get_latest = _make_use_case()
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)

    with pytest.raises(SerProviderSessionNotFoundError):
        uc.execute(
            user_id=_OWNER,
            vehicle_id=vehicle.id,
            provider="madrid_ser_app",
            duration_minutes=60,
            location=GeoLocation(lat=40.0, lng=-3.0),
        )

    assert provider.create_ticket_calls == []


def test_unregistered_provider_raises_provider_not_found() -> None:
    vehicle_repo = InMemoryVehicleRepo()
    config_repo = InMemoryUserSerProviderConfigRepo()
    ticket_repo = InMemoryParkingTicketRepo()
    uc = CreateSerTicket(
        vehicle_repo=vehicle_repo,
        config_repo=config_repo,
        ticket_repo=ticket_repo,
        providers={},
        event_publisher=FakeEventPublisher(),
        get_latest_vehicle_location=FakeGetLatestVehicleLocation(),
    )

    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={}))

    with pytest.raises(SerTicketProviderNotFoundError):
        uc.execute(
            user_id=_OWNER,
            vehicle_id=vehicle.id,
            provider="madrid_ser_app",
            duration_minutes=60,
            location=GeoLocation(lat=40.0, lng=-3.0),
        )

    assert ticket_repo.saved == []


def test_ticket_repo_save_failure_is_logged_and_raised_as_persistence_error_after_exhausting_retries(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """
    The provider already created the real ticket by this point. A save
    failure is retried a bounded number of times (`_TICKET_SAVE_MAX_ATTEMPTS`)
    before surfacing as SerTicketPersistenceError (not a bare re-raise of the
    underlying exception), chained via `from`, so callers can distinguish
    "charged but unpersisted" from any other creation failure (see this
    fix's docstring note in create_ser_ticket.py). The retry delay is
    monkeypatched to 0 so the test stays fast.
    """
    monkeypatch.setattr("mobility_manager.application.use_cases.create_ser_ticket._TICKET_SAVE_RETRY_DELAY_SECONDS", 0)
    vehicle_repo = InMemoryVehicleRepo()
    config_repo = InMemoryUserSerProviderConfigRepo()
    ticket_repo = InMemoryParkingTicketRepo(raise_on_save=True)
    provider = FakeSerTicketProvider()
    uc = CreateSerTicket(
        vehicle_repo=vehicle_repo,
        config_repo=config_repo,
        ticket_repo=ticket_repo,
        providers={"madrid_ser_app": provider},
        event_publisher=FakeEventPublisher(),
        get_latest_vehicle_location=FakeGetLatestVehicleLocation(),
    )
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={"token": "abc"}))

    with caplog.at_level("ERROR"), pytest.raises(SerTicketPersistenceError) as exc_info:
        uc.execute(
            user_id=_OWNER,
            vehicle_id=vehicle.id,
            provider="madrid_ser_app",
            duration_minutes=60,
            location=GeoLocation(lat=40.0, lng=-3.0),
        )

    assert isinstance(exc_info.value.__cause__, RuntimeError)
    assert ticket_repo.saved == []
    assert ticket_repo.save_calls == 3
    assert any("Failed to persist ParkingTicket" in record.message for record in caplog.records)


def test_ticket_repo_save_succeeds_after_transient_failures_no_exception_raised(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    A save that fails once or twice (transient blip: query timeout,
    deadlock, momentary connection loss) but succeeds within the bounded
    retry budget must persist the ticket normally, with no exception raised
    — this is the fix for the financial-risk regression where a persistence
    failure after a real provider charge would otherwise be indistinguishable
    from "no ticket ever existed", causing SerZoneRecheckGate/
    SerTicketCreationTriggerHandler to keep retrying the real charge on every
    poll. The retry delay is monkeypatched to 0 so the test stays fast.
    """
    monkeypatch.setattr("mobility_manager.application.use_cases.create_ser_ticket._TICKET_SAVE_RETRY_DELAY_SECONDS", 0)
    vehicle_repo = InMemoryVehicleRepo()
    config_repo = InMemoryUserSerProviderConfigRepo()
    ticket_repo = InMemoryParkingTicketRepo(fail_first_n_saves=2)
    provider = FakeSerTicketProvider()
    uc = CreateSerTicket(
        vehicle_repo=vehicle_repo,
        config_repo=config_repo,
        ticket_repo=ticket_repo,
        providers={"madrid_ser_app": provider},
        event_publisher=FakeEventPublisher(),
        get_latest_vehicle_location=FakeGetLatestVehicleLocation(),
    )
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={"token": "abc"}))

    result = uc.execute(
        user_id=_OWNER,
        vehicle_id=vehicle.id,
        provider="madrid_ser_app",
        duration_minutes=60,
        location=GeoLocation(lat=40.0, lng=-3.0),
    )

    assert ticket_repo.save_calls == 3
    assert ticket_repo.saved == [result]


def test_vehicle_not_present_in_provider_publishes_event_and_reraises() -> None:
    provider = FakeSerTicketProvider(raise_vehicle_not_found=True)
    uc, vehicle_repo, config_repo, ticket_repo, provider, event_publisher, _get_latest = _make_use_case(
        provider=provider
    )
    vehicle = _make_vehicle(_OWNER)
    vehicle_repo.add(vehicle)
    config_repo.add(_OWNER, "madrid_ser_app", SerProviderSession(data={"token": "abc"}))

    with pytest.raises(SerProviderVehicleNotFoundError):
        uc.execute(
            user_id=_OWNER,
            vehicle_id=vehicle.id,
            provider="madrid_ser_app",
            duration_minutes=60,
            location=GeoLocation(lat=40.0, lng=-3.0),
        )

    assert ticket_repo.saved == []
    assert len(event_publisher.published) == 1
    event = event_publisher.published[0]
    assert isinstance(event, VehicleNotPresentInSerTicketProvider)
    assert event.vehicle_id == vehicle.id
    assert event.user_id == _OWNER
    assert event.provider == "madrid_ser_app"
