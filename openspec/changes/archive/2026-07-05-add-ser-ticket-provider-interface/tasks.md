## 1. Domain layer — ser-ticket-provider

- [x] 1.1 `domain/entities/parking_ticket.py` — replace the empty stub with a frozen dataclass `ParkingTicket`: `id: UUID`, `vehicle_id: UUID`, `user_id: UUID`, `provider: str`, `duration_minutes: int`, `provider_reference: str | None`, `created_at: datetime`
- [x] 1.2a `domain/value_objects/ser_provider_credentials.py` and `domain/value_objects/ser_provider_session.py` — frozen dataclasses `SerProviderCredentials` and `SerProviderSession`, each wrapping a single `data: dict[str, Any]` field. Mirrors `ToyotaConfig`'s role (a named, typed value crosses the port boundary rather than a bare dict) — these are intentionally thin wrappers since the concrete payload shape isn't known yet.
- [x] 1.2 `domain/ports/ser_ticket_provider.py` — replace the empty `ParkingServicePort` stub's role: define `SerTicketProviderPort(ABC)` with `login(self, credentials: SerProviderCredentials) -> SerProviderSession` and `create_ticket(self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int) -> ParkingTicket`. Leave `domain/ports/parking_service.py` alone (unrelated tombstone-style stub) unless it's clearly meant to be replaced — confirm naming doesn't collide before deleting anything.
- [x] 1.3 `domain/ports/user_ser_provider_config_repository.py` — abstract `UserSerProviderConfigRepository` with `save(user_id: UUID, provider: str, session: SerProviderSession) -> None` and `find(user_id: UUID, provider: str) -> SerProviderSession | None`
- [x] 1.4 `domain/ports/parking_ticket_repository.py` — abstract `ParkingTicketRepository` with `save(ticket: ParkingTicket) -> None`
- [x] 1.5 Add new exceptions to `domain/exceptions.py`: `SerTicketProviderNotFoundError` (unknown provider name in registry), `SerProviderSessionNotFoundError` (no stored session for a `(user_id, provider)` pair) — following the existing `class XError(Exception): pass` style. Note: `SerTicketProviderRegistry` itself is infrastructure-only, with no abstract domain port — mirrors `BrandRegistry`, which is a concrete infrastructure class with no domain-level counterpart (see task 3.1).

## 2. Domain layer — vehicle-location-events

- [x] 2.1 `domain/events/__init__.py` and `domain/events/vehicle_location_updated.py` — new `domain/events/` package (first of its kind in this codebase, mirrors `domain/entities/`/`domain/value_objects/` structure); frozen dataclass `VehicleLocationUpdated`: `vehicle_id: UUID`, `latitude: float`, `longitude: float`, `recorded_at: datetime`, `source: Literal["pull", "push"]`
- [x] 2.2 `domain/ports/event_publisher.py` — abstract `EventPublisher(ABC)` with `publish(self, event: object) -> None` (or a minimal `DomainEvent` marker base class if preferred for typing — keep it lightweight, no framework dependency)

## 3. Infrastructure layer — ser-ticket-provider

- [x] 3.1 `infrastructure/ser_ticket_providers/registry.py` — `SerTicketProviderRegistry` mirroring `infrastructure/vehicle_providers/brand_registry.py`'s shape: a method returning the currently available providers keyed by name (e.g. `dict[str, SerTicketProviderPort]`), returning an empty dict since no concrete provider is registered yet. No env-var parsing needed yet (nothing to enable) — keep the mechanism ready for a future provider to register itself, following the same pattern `BrandRegistry` uses for brand codes.
- [x] 3.2 Alembic migration: `user_ser_provider_configs` table — `user_id UUID NOT NULL REFERENCES users(id)`, `provider TEXT NOT NULL`, `encrypted_payload BYTEA NOT NULL`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`, composite PK `(user_id, provider)`
- [x] 3.3 Alembic migration: `parking_tickets` table — `id UUID PRIMARY KEY`, `vehicle_id UUID NOT NULL REFERENCES vehicles(id)`, `user_id UUID NOT NULL REFERENCES users(id)`, `provider TEXT NOT NULL`, `duration_minutes INT NOT NULL`, `provider_reference TEXT`, `created_at TIMESTAMP WITH TIME ZONE NOT NULL`
- [x] 3.4 Add `user_ser_provider_configs_table` and `parking_tickets_table` to `infrastructure/orm/tables.py`
- [x] 3.5 `infrastructure/repositories/postgres/user_ser_provider_config_repo.py` — `PostgresUserSerProviderConfigRepository` implementing `UserSerProviderConfigRepository`: `save` JSON-serializes + Fernet-encrypts `session.data` (reuse `infrastructure/crypto.py`'s `encrypt`/`decrypt`, same as `PostgresVehicleConfigRepository`) and upserts by `(user_id, provider)`; `find` decrypts + deserializes, wraps the result in a `SerProviderSession`, returns `None` if no row
- [x] 3.6 `infrastructure/repositories/postgres/parking_ticket_repo.py` — `PostgresParkingTicketRepository` implementing `ParkingTicketRepository.save`

## 4. Infrastructure layer — vehicle-location-events

- [x] 4.1 `infrastructure/events/in_memory_event_publisher.py` — `InMemoryEventPublisher` implementing `EventPublisher`: internal `dict[type, list[Callable]]`, `subscribe(event_type: type, handler: Callable) -> None` to register, `publish(event) -> None` synchronously invokes every handler registered for `type(event)` (no-op if none registered)

## 5. Application layer — ser-ticket-provider

- [x] 5.1 `application/use_cases/connect_ser_ticket_provider.py` — `ConnectSerTicketProvider` use case: `execute(user_id: UUID, provider: str, credentials: SerProviderCredentials) -> None`. Look up the provider in `SerTicketProviderRegistry`; raise `SerTicketProviderNotFoundError` if absent; call `provider.login(credentials)`; persist the resulting `SerProviderSession` via `UserSerProviderConfigRepository.save`.
- [x] 5.2 `application/use_cases/create_ser_ticket.py` — `CreateSerTicket` use case: `execute(user_id: UUID, vehicle_id: UUID, provider: str, duration_minutes: int) -> ParkingTicket`. Look up the vehicle via `VehicleRepository`; raise `VehicleNotFoundError` if missing OR if `vehicle.user_id != user_id` (indistinguishable from "not found" to avoid leaking ownership info, consistent with treating unauthorized access as absence). Look up the session via `UserSerProviderConfigRepository.find`; raise `SerProviderSessionNotFoundError` if `None`. Resolve the provider instance from the registry (raise `SerTicketProviderNotFoundError` if absent — should not normally happen if a session exists, but don't assume). Call `provider.create_ticket(session, vehicle, duration_minutes)`, persist the result via `ParkingTicketRepository.save`, return it.

## 6. Application layer — vehicle-location-events

- [x] 6.1 `application/event_handlers/__init__.py` and `application/event_handlers/ser_ticket_trigger_handler.py` — `SerTicketTriggerHandler` with a `handle(self, event: VehicleLocationUpdated) -> None` method whose body is a no-op (e.g. `pass`, or a debug-level log line at most) — no SER zone lookup, no preference lookup, no ticket creation
- [x] 6.2 Update `application/use_cases/record_vehicle_location.py`: accept an `EventPublisher` in `__init__`, and after `self._location_repo.save(location)` succeeds, call `self._event_publisher.publish(VehicleLocationUpdated(vehicle_id=..., latitude=lat, longitude=lon, recorded_at=recorded_at_utc, source=source))`. Do not publish if validation raised before the save.

## 7. Wiring

- [x] 7.1 In `app.py`: construct `InMemoryEventPublisher`, construct `SerTicketTriggerHandler`, call `publisher.subscribe(VehicleLocationUpdated, handler.handle)` at startup, pass the publisher into `RecordVehicleLocation`'s constructor (both the scheduler-facing and endpoint-facing instances — check whether `record_vehicle_location.py` is constructed once and shared or built per-caller; keep it a single shared instance if that's the existing pattern)
- [x] 7.2 In `app.py`: construct `SerTicketProviderRegistry`, `PostgresUserSerProviderConfigRepository`, `PostgresParkingTicketRepository`, `ConnectSerTicketProvider`, `CreateSerTicket`, and store them on `app.state` (even though no router uses them yet, mirroring how other use cases are wired for future router access)

## 8. Backend tests

- [x] 8.1 `tests/infrastructure/test_user_ser_provider_config_repo_integration.py` — save/find round-trip, `find` returns `None` when absent, upsert overwrites an existing row for the same `(user_id, provider)`
- [x] 8.2 `tests/infrastructure/test_parking_ticket_repo_integration.py` — `save` persists all fields correctly, including `provider_reference=None`
- [x] 8.3 `tests/infrastructure/test_in_memory_event_publisher.py` — subscribed handler invoked synchronously on publish; publish with no subscribers is a no-op; multiple handlers for the same event type are all invoked
- [x] 8.4 `tests/application/use_cases/test_connect_ser_ticket_provider.py` — successful connection persists the `SerProviderSession` (against a fake `SerTicketProviderPort`); unknown provider raises `SerTicketProviderNotFoundError` without calling anything
- [x] 8.5 `tests/application/use_cases/test_create_ser_ticket.py` — successful creation (fake provider) persists and returns the ticket; vehicle not owned by user raises `VehicleNotFoundError`; missing session raises `SerProviderSessionNotFoundError`
- [x] 8.6 Update `tests/application/use_cases/test_record_vehicle_location.py` (or create if it doesn't exist — check first) to assert a `VehicleLocationUpdated` event is published (via a fake/spy `EventPublisher`) after a successful save, with the correct `source`, and that no event is published when validation raises
- [x] 8.7 `tests/application/event_handlers/test_ser_ticket_trigger_handler.py` — handler can be invoked with a `VehicleLocationUpdated` event and produces no observable side effects (nothing to assert beyond "doesn't raise" — document why the test is intentionally minimal)

## 9. Verification

- [x] 9.1 Run backend test suite and linters (ruff, mypy) per project convention
- [x] 9.2 Confirm no behavior change for existing vehicle-location-pull/push flows: run existing location-related tests and confirm they still pass unmodified (aside from picking up the new `EventPublisher` constructor dependency where `RecordVehicleLocation` is instantiated in tests)
