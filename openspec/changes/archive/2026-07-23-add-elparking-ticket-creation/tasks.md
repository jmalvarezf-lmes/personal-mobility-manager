## 1. Domain layer

- [x] 1.1 Add `SerProviderVehicleNotFoundError` to `domain/exceptions.py`, following the existing `class XError(Exception): pass` style
- [x] 1.2 Add `domain/events/vehicle_not_present_in_ser_ticket_provider.py` — frozen dataclass `VehicleNotPresentInSerTicketProvider` with `vehicle_id: UUID`, `user_id: UUID`, `provider: str`, mirroring `VehicleLocationUpdated`'s shape
- [x] 1.3 Update `domain/entities/parking_ticket.py`: add `cost: float` and `end_date: datetime` fields to the frozen `ParkingTicket` dataclass
- [x] 1.4 Update `domain/ports/ser_ticket_provider.py`: `create_ticket` gains a required `location: GeoLocation` parameter; update the abstract method's docstring accordingly

## 2. Infrastructure layer — ElParkingClient

- [x] 2.1 Add `infrastructure/ser_ticket_providers/elparking/client.py` — `ElParkingClient`, constructed with `base_url` and `app_version`:
  - `_auth_headers() -> dict` private helper returning `ep-app-name`/`ep-app-version` headers (shared by every method except `login`)
  - `_basic_auth(access_token: str) -> httpx.BasicAuth` private helper returning `httpx.BasicAuth("", access_token)`
  - `login(credentials: SerProviderCredentials) -> SerProviderSession` — moved from `provider.py` unchanged in behavior
  - `logout(access_token: str) -> None` — `DELETE /v1/logins/{access_token}`, using `_basic_auth`/`_auth_headers` instead of the current `Authorization: Bearer` header (bug fix)
  - `list_vehicles(access_token: str) -> list[dict]` — `GET /v1/users/me/vehicles`
  - `list_towns(access_token: str) -> list[dict]` — `GET /v1/ser-towns`
  - `list_zones(access_token: str, town_id: str) -> list[dict]` — `GET /v1/ser-zones/<townId>`
  - `get_steps(access_token: str, zone_id: str, rate_id: str, vehicle_id: int) -> dict` — `GET /v1/ser-steps/zone/<zoneId>/rate/<rateId>/vehicle/<vehicleId>`
  - `create_ticket(access_token: str, body: dict) -> dict` — `POST /v1/ser-tickets`
  - Every method wraps `httpx.HTTPError` and non-2xx/malformed responses as `SerProviderApiError`, consistent with the existing `login`/`logout` failure vocabulary
- [x] 2.2 Update `infrastructure/ser_ticket_providers/elparking/provider.py`: remove the inline `httpx` calls from `login`/`logout`, delegate both to a constructor-injected `ElParkingClient` instance instead

## 3. Infrastructure layer — ElParking zone-mapping cache

- [x] 3.1 Add Alembic migration creating `ser_ticket_provider_zone_mappings` (name kept provider-agnostic since `provider` is already a column, not baked into the table name): `city_code TEXT NOT NULL`, `provider TEXT NOT NULL`, `id_ser_town TEXT NOT NULL`, `zones_payload JSONB NOT NULL` (raw fetched zones incl. `id`, `name`, `polygon_wkt`, `rates[]`), `fetched_at TIMESTAMPTZ NOT NULL`, composite primary key `(city_code, provider)`
- [x] 3.2 Add `infrastructure/ser_ticket_providers/elparking/zone_mapping_repository.py` — infra-internal repository (not a domain port): `get(city_code: str, provider: str) -> ElParkingZoneMapping | None` (returns `None` if missing or `fetched_at` older than 30 days), `save(city_code: str, provider: str, mapping: ElParkingZoneMapping) -> None` (upsert with current timestamp)
- [x] 3.3 Add `infrastructure/ser_ticket_providers/elparking/zone_mapping.py` — small internal dataclass(es) representing a cached town + its zones + each zone's rates + polygon, kept entirely inside this package (never imported by domain/application code)
- [x] 3.4 Add `infrastructure/ser_ticket_providers/elparking/zone_resolver.py` (or a private method group on the provider) implementing the resolution algorithm from design.md decision 3:
  - town: match `City.name` (via injected `CityRepository`) case-insensitively against cached/fetched town names
  - zone: match `zone_number` (zero-padded) against each cached zone's name-leading-number; when multiple candidates share a `zone_number`, parse each candidate's `polygon_wkt` with shapely and pick the one containing `location` (reprojected the same way `SerZone.contains()` does)
  - rate: match `zone_type` (stripped of a `"Tarifa "` prefix, case/accent-insensitive) against the resolved zone's cached rate names

## 4. Infrastructure layer — ElParkingSerTicketProvider.create_ticket

- [x] 4.1 Update `ElParkingSerTicketProvider.__init__` to accept `ser_zone_repo: SerZoneRepository`, `city_repo: CityRepository`, and the zone-mapping repository from 3.2, alongside the existing `base_url`/`app_version`-derived `ElParkingClient`
- [x] 4.2 Implement `create_ticket(session, vehicle, duration_minutes, location) -> ParkingTicket`:
  1. Call `client.list_vehicles(access_token)`, match by `vehicle.license_plate`; raise `SerProviderVehicleNotFoundError` on no match
  2. Call `ser_zone_repo.find_containing(location)`; if `None`, raise the appropriate existing not-found error (mirror how `FindContainingSerZone` callers already treat "no zone" — decide the exact error at implementation time, consistent with `SerZoneNotFoundError`'s existing usage)
  3. Resolve `id_ser_town`/`id_ser_zone`/`id_ser_rate` via the zone-mapping cache (3.2) and resolver (3.4), fetching via `ElParkingClient` on a cache miss/stale entry and persisting the result
  4. Call `client.get_steps(...)`, select the `steps[]` entry whose `stay_duration == duration_minutes`, extract `fare_qty`
  5. Build the `POST /v1/ser-tickets` body (per design.md's field table) using the resolved IDs, `location`'s lat/lng, `duration_minutes`, `fare_qty`, and the verbatim `step_request`
  6. Call `client.create_ticket(...)`; map the response into a `ParkingTicket` (`cost` from `total_qty`, `end_date` parsed from the response, `provider_reference` from the ticket id)
- [x] 4.3 Remove the `NotImplementedError` stub and its module docstring note

## 5. Infrastructure layer — parking_tickets persistence

- [x] 5.1 Add Alembic migration adding `cost NUMERIC NOT NULL` and `end_date TIMESTAMPTZ NOT NULL` columns to `parking_tickets`
- [x] 5.2 Update `infrastructure/repositories/postgres/parking_ticket_repo.py` to read/write the two new columns

## 6. Application layer — CreateSerTicket

- [x] 6.1 Update `CreateSerTicket.__init__` to accept an injected `EventPublisher` and a `GetLatestVehicleLocation` use case
- [x] 6.2 Update `CreateSerTicket.execute` signature to `execute(self, user_id, vehicle_id, provider, duration_minutes, location: GeoLocation | None = None) -> ParkingTicket`:
  - When `location` is `None`, resolve it via `GetLatestVehicleLocation.execute(vehicle_id)` before calling the provider
  - Wrap the provider's `create_ticket` call in a `try/except SerProviderVehicleNotFoundError`, publishing `VehicleNotPresentInSerTicketProvider(vehicle_id, user_id, provider)` before re-raising

## 7. Wiring

- [x] 7.1 Update `SerTicketProviderRegistry.build_providers()` to accept `ser_zone_repo`, `city_repo`, and the zone-mapping repository, threading them into `ElParkingSerTicketProvider`'s constructor
- [x] 7.2 Update `app.py`: pass `ser_zone_repo`/`city_repo` (already constructed earlier in startup) and a newly-constructed `PostgresElParkingZoneMappingRepository`(or equivalent) into `SerTicketProviderRegistry.build_providers(...)`; pass the existing `event_publisher` and a `GetLatestVehicleLocation` instance into `CreateSerTicket`

## 8. Presentation layer

- [x] 8.1 Add `CreateSerTicketRequest`/`ParkingTicketResponse` schemas to `presentation/api/schemas.py`: request has `vehicle_id: UUID`, `provider: str`, `duration_minutes: int`, `latitude: float | None`, `longitude: float | None`; response has `id`, `cost`, `end_date`, `provider_reference`, `duration_minutes`
- [x] 8.2 Add `POST /parking/ser-tickets` to `presentation/api/routers/parking.py`: authenticated via existing session dependency; builds an optional `GeoLocation` only when both `latitude`/`longitude` are present; calls `request.app.state.create_ser_ticket.execute(...)`; maps `VehicleNotFoundError`/`SerProviderSessionNotFoundError` → 404, `SerProviderVehicleNotFoundError` → 409, `SerProviderApiError` → 502; returns `201 Created` on success

## 9. Backend tests

- [x] 9.1 `tests/infrastructure/test_elparking_client.py` — unit tests for every `ElParkingClient` method against a mocked `httpx` transport: confirms HTTP Basic auth (blank username, access token as password) and the `ep-app-name`/`ep-app-version` headers on every authenticated call; confirms `logout` no longer sends `Authorization: Bearer`
- [x] 9.2 Update `tests/infrastructure/test_elparking_provider.py`: remove the `create_ticket` "raises NotImplementedError" test; add coverage for the full resolution + submission flow (fake `ElParkingClient`, fake `SerZoneRepository`/`CityRepository`/zone-mapping repository) including the duplicate-zone_number polygon-disambiguation path and the vehicle-not-found path
- [x] 9.3 `tests/infrastructure/test_elparking_zone_mapping_repository.py` — cache save/get round-trip, freshness boundary at 30 days
- [x] 9.4 Update `tests/application/use_cases/test_create_ser_ticket.py`: location fallback via a fake `GetLatestVehicleLocation`, explicit location bypasses the fallback, `VehicleNotPresentInSerTicketProvider` is published (and the use case still raises) when the provider raises `SerProviderVehicleNotFoundError`
- [x] 9.5 Update `tests/infrastructure/test_ser_ticket_provider_registry.py` for the widened `build_providers()` signature
- [x] 9.6 `tests/presentation/test_parking_router.py` (extend existing) — `POST /parking/ser-tickets` happy path (with and without explicit lat/lng), 404/409/502/401 mappings

## 10. Verification

- [x] 10.1 Run `make test` and `make coverage` — confirm `domain/` stays at 100% and `application/` at 80%+ (see note below: `make test`'s hardcoded `POSTGRES_DSN` requires a live local Postgres this sandbox doesn't have; verified instead via `POSTGRES_DSN="" venv/bin/python -m pytest tests/ --cov=mobility_manager --cov-report=term-missing`, which correctly skips the 116 Postgres-integration tests per AGENTS.md's documented carve-out. Result: 749 passed, 116 skipped, 0 failed. `domain/` = 99.56% — the only gap is `domain/ports/parking_service.py` (2 lines), a pre-existing, untouched "tombstone stub" from commit `3c522e4` (unrelated to this change, confirmed via `git diff`/`git log` — not part of this diff). Every domain file this change added or touched is at 100%. `application/` = 98.15%, comfortably above the 80% target; every application file this change added or touched (`create_ser_ticket.py`) is at 100%. No separate `make coverage` Makefile target exists — `make test` already runs with `--cov`, matching AGENTS.md's "or `pytest --cov=...`" alternative.)
- [x] 10.2 Run linters/type-checks per project convention (`make lint`: ruff clean, mypy clean — 0 errors across 188 source files)
- [ ] 10.3 Manually verify `POST /parking/ser-tickets` end-to-end against the live ElParking API with a real connected account and a vehicle whose plate is registered there; confirm the Basic-auth fix and header requirements hold for every new endpoint, not just the ones already covered by unit tests — **left unchecked**: this environment has no real ElParking credentials or network access to the live API, exactly as task 8.3 was left unchecked for the same reason in the archived `add-elparking-login-provider` change's `tasks.md`. Every ASSUMPTION documented inline in `provider.py`/`client.py` (vehicle-match field names, ticket body field names, response field names, login's invalid-credentials status code) remains unverified against the real API and should be confirmed by whoever performs this manual step.

## 11. Fixes from 4R review

A 4R review (risk, resilience, readability, reliability — run directly, not via the gentle-ai lifecycle) found the following on the implementation from sections 1-9. Findings converged independently across reviewers where noted.

- [x] 11.1 `presentation/api/routers/parking.py`: `POST /parking/ser-tickets` catches only `VehicleNotFoundError`/`SerProviderSessionNotFoundError` (404), `SerProviderVehicleNotFoundError` (409), and `SerProviderApiError` (502) — add `SerZoneNotFoundError` (vehicle's location isn't inside any known SER zone), `VehicleLocationNotFoundError` (no explicit lat/lng and the vehicle has no location history), and `SerTicketProviderNotFoundError` (unknown `provider` name) to the except clauses, mapping all three to `404 Not Found`, mirroring the existing `SerZoneNotFoundError` handling in this same file's `GET /parking/ser-zone` and `VehicleLocationNotFoundError`/`SerTicketProviderNotFoundError` handling already established in `vehicles.py`/`ser_ticket_providers.py`. **[CRITICAL — found independently by two reviewers]**
- [x] 11.2 `application/use_cases/create_ser_ticket.py`: update `execute()`'s docstring `Raises:` section to also document `SerZoneNotFoundError` and `SerProviderApiError`, which can propagate unmodified from the provider call today but aren't currently listed
- [x] 11.3 `infrastructure/ser_ticket_providers/elparking/provider.py`: wrap the zone/rate/step list parsing (`_get_or_refresh_mapping`, `_select_step`) and the final `create_ticket` response parsing in `try/except (KeyError, TypeError, IndexError)`, raising `SerProviderApiError` with a clear message — a malformed/unexpected-shape upstream response currently raises a raw uncaught exception instead of the established failure vocabulary. While doing this, extract the `POST /v1/ser-tickets` request-body construction and response-to-`ParkingTicket` mapping into named helpers (e.g. `_build_ticket_request_body`/`_parse_ticket_response`), matching the existing `_match_vehicle`/`_select_step`/`_get_or_refresh_mapping` extraction pattern already used earlier in the same method — this also isolates the two documented `ASSUMPTION` blocks for easier future correction.
- [x] 11.4 `infrastructure/ser_ticket_providers/elparking/zone_mapping_repository.py`: wrap `get()`'s `zones_payload` deserialization in `try/except (KeyError, TypeError)` — a structurally malformed cache row should be treated as a cache miss (log a warning, return `None`, let the caller re-fetch) rather than crash with an uncaught `KeyError`
- [x] 11.5 `application/use_cases/create_ser_ticket.py`: wrap `self._ticket_repo.save(ticket)` (which runs only after the provider has already created/charged the real ticket) in `try/except`: on failure, log at `ERROR` with `vehicle_id`/`user_id`/`provider`/`provider_reference`/`cost`/`end_date` so a lost local record can be manually reconciled against the provider's own records, then re-raise — mirrors `register_vehicle.py`'s established pattern of logging around a post-critical-write side effect, applied here to a higher-stakes (real financial transaction) case that currently has zero logging in the entire module. **[BLOCKER]**
- [x] 11.6 Add missing test coverage identified by review: router 404 mapping for the three exceptions added in 11.1; `zone_resolver` edge cases (case/diacritic-insensitive town matching, zero matching zone_number candidates, more than two duplicate-zone_number candidates, no matching rate); provider `create_ticket` edge cases (no city registered for a zone's `city_code`, no ElParking town match, no rate match, no pricing step for the requested duration, malformed ticket-creation response missing `total_qty`/`end_date`); `zone_mapping_repository` malformed-row handling from 11.4 (added `tests/presentation/test_parking_router.py::test_ser_zone_not_found_returns_404`/`test_vehicle_location_not_found_returns_404`/`test_unknown_provider_returns_404`; new `tests/infrastructure/test_elparking_zone_resolver.py`; extended `tests/infrastructure/test_elparking_provider.py` with city/town/rate/step/malformed-response edge cases plus 11.3's new malformed-shape branches; extended `tests/infrastructure/test_elparking_zone_mapping_repository.py` with `test_get_returns_none_for_malformed_zones_payload`; added `tests/application/use_cases/test_create_ser_ticket.py::test_ticket_repo_save_failure_is_logged_and_reraised` for 11.5)
- [x] 11.7 Run `make test` and `make coverage` — confirm still green and `domain`/`application` coverage targets still hold after these fixes (verified via `POSTGRES_DSN="" venv/bin/python -m pytest tests/ --cov=mobility_manager --cov-report=term-missing`: 772 passed, 117 skipped, 0 failed. Every file touched by this fix batch — `parking.py`, `create_ser_ticket.py`, `provider.py`, `zone_resolver.py` — is at 100% coverage. `domain/`'s only gap remains the pre-existing, unrelated `domain/ports/parking_service.py` tombstone stub noted in 10.1. `make lint` (ruff + mypy) is clean.)

**Explicitly deferred, not fixed in this change** (raised by review, judged to need a product decision rather than a silent fix):
- No idempotency-key protection on `POST /parking/ser-tickets` — a client retry across the up-to-6-call chain could create a second real ElParking charge. Fixing this means changing the request/response contract (an idempotency key, dedup storage), which is a scope decision, not a bug fix.
- No per-`(city_code, provider)` lock on the zone-mapping cache's cold-cache fetch path — concurrent requests during a cache-miss window each independently re-fetch from ElParking. The existing `ON CONFLICT` upsert keeps this *correct*, just not maximally efficient; accepted as a trade-off consistent with design.md's existing risk-acceptance language.
