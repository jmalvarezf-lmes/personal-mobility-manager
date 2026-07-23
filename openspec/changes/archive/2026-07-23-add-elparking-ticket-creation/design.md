## Context

`SerTicketProviderPort`, `ParkingTicket`, `CreateSerTicket`, and `ElParkingSerTicketProvider.login()`/`logout()` already exist (`add-ser-ticket-provider-interface`, `add-elparking-login-provider`, both archived 2026-07-05). `create_ticket()` is a deliberate `NotImplementedError` stub — this is the "later change" both of those designs pointed to.

ElParking's real ticket-creation flow (`POST /v1/ser-tickets`) requires five prerequisite lookups in order: the user's ElParking vehicle list (to get `id_vehicle`), SER towns (`id_ser_town`), that town's zones (`id_ser_zone`), that zone's rates (`id_ser_rate`), and a mandatory, time-sensitive pricing/checksum step (`GET /v1/ser-steps/...`) whose response (`step_request`) must be forwarded verbatim — the server re-validates its `security_checksum` and rejects stale requests via `SerStepsOutOfDateException`. None of this may leak past `SerTicketProviderPort` — a future non-ElParking provider, and the already-scaffolded (but still no-op) `SerTicketTriggerHandler` → automatic ticket creation path, must never need to know any of it.

Research against real ElParking API dumps (`ser-towns.json`, `ser-zones.json`, sampled 2026-07-23) established:
- ElParking towns are matched to our `cities` table by name, case-insensitively (`SERTown.name` vs `City.name`).
- Within a town, ElParking zones are matched to our own `SerZone.zone_number` via the zone's `name` field's leading number (e.g. `"84 - PILAR"` → `84`, zero-padded to 3 digits). This is reliable for 62/71 sampled Madrid zones; the other 9 zone_numbers are each split across two disjoint ElParking zone records (same `rates[]`, different `polygon_wkt`) — the zone `id` suffix is NOT a reliable zone_number encoding (mismatches in the same 9 cases).
- Rate selection matches `zones[].rates[].name` against our own `SerZone.zone_type` (e.g. `Azul` → `"Tarifa Azul"`), stripping the `"Tarifa "` prefix, case/accent-insensitive. This lines up exactly with `MadridZoneType`'s existing values.
- Both endpoints require a valid session, but their response content is user-agnostic (same for any authenticated caller) and stable — reference data, not per-user state.
- ElParking's authenticated endpoints (confirmed by the user, not just `login`) use HTTP Basic auth with a blank username and the access token as the password — not `Authorization: Bearer`. The existing `logout()` implementation uses Bearer and is wrong; this was already flagged as an unverified assumption in that code.

## Goals / Non-Goals

**Goals:**
- Implement `ElParkingSerTicketProvider.create_ticket()` end-to-end against the real API, entirely hidden behind the unchanged shape of `SerTicketProviderPort` (aside from adding `location`).
- Reuse our own SER zone geometry (`FindContainingSerZone`/`SerZoneRepository`) as the primary spatial resolver; only consult ElParking's own zone polygons to disambiguate the rare same-zone_number-multiple-records case.
- Cache ElParking's town/zone/rate ID-translation data per `(city_code, provider)`, refreshed lazily, valid for 30 days.
- Widen `ParkingTicket` with `cost`/`end_date` and expose ticket creation over HTTP.
- Emit `VehicleNotPresentInSerTicketProvider` when the vehicle can't be matched on ElParking's side, without building a notification handler for it yet.
- Fix `logout()`'s auth scheme as part of consolidating all ElParking HTTP calls into one client.
- Keep the design directly reusable, unmodified, by the future `VehicleLocationUpdated` → automatic-creation trigger.

**Non-Goals:**
- No automatic ticket creation from `VehicleLocationUpdated` in this change — `SerTicketTriggerHandler` stays notification-only; this change only makes sure `CreateSerTicket`/`create_ticket()` are shaped so that a later change can call them from the handler with zero changes to their signatures.
- No handler for `VehicleNotPresentInSerTicketProvider` (no notification is sent yet) — event only, mirroring how `VehicleLocationUpdated` shipped before `SerTicketTriggerHandler` existed.
- No session renewal logic for expired ElParking sessions — out of scope, as originally decided in `add-ser-ticket-provider-interface`.
- No support for `TYPE_EXTENDED` (extending an existing active ticket) — only `TYPE_NORMAL` (the default) is created.
- No background/scheduled refresh job for the ElParking zone-mapping cache — refresh is lazy, triggered by the next ticket-creation request past the 30-day window.
- No idempotency-key protection on `POST /parking/ser-tickets` against client-retry double-charging. This endpoint is a manual/testing surface, not the intended production trigger — the real production path is the future `VehicleLocationUpdated`-based auto-creation (see Goals above), which has no HTTP caller and therefore no retry surface to begin with. Revisit this decision if `POST /parking/ser-tickets` is ever exposed to a real client instead of staying a testing/manual-trigger endpoint.

## Decisions

### 1. `ElParkingClient` centralizes all HTTP mechanics
A new `infrastructure/ser_ticket_providers/elparking/client.py` wraps every ElParking HTTP call (`login`, `logout`, `list_vehicles`, `list_towns`, `list_zones`, `get_steps`, `create_ticket`) behind one `httpx.Client`-based class. Every authenticated call uses `httpx.BasicAuth("", access_token)` plus the same `ep-app-name`/`ep-app-version` headers `login()` already sends. `ElParkingSerTicketProvider` becomes a thin orchestrator that calls `ElParkingClient` methods and applies resolution/caching logic; it no longer builds `httpx` requests itself.

Alternative considered: keep all HTTP calls inline in `ElParkingSerTicketProvider`, as `login`/`logout` do today. Rejected — `create_ticket()` alone needs 5-6 authenticated calls, and duplicating auth+header construction that many times is exactly the kind of repetition a thin client class exists to remove; it also isolates the Basic-auth fix to one place.

### 2. `logout()`'s auth bug is fixed as part of this change
`logout()` moves into `ElParkingClient.logout()` and switches from `Authorization: Bearer {access_token}` to `httpx.BasicAuth("", access_token)`, consistent with every other authenticated endpoint. This is a corrective fix to already-shipped code, bundled here because it shares the exact same auth mechanism this change is implementing everywhere else — not deferring it would mean shipping a second, differently-broken auth pattern in the same class.

### 3. Zone/rate resolution: our own geometry first, ElParking's only to disambiguate
```
location → FindContainingSerZone (existing) → SerZone(city_code, zone_number, zone_type)
city_code → CityRepository.list_all() → match City.name vs cached/fetched SERTown.name (case-insensitive) → id_ser_town
id_ser_town → cached zones[] → filter by name-leading-number == zone_number
    → 1 match: done
    → >1 match: point-in-polygon against each candidate's polygon_wkt (shapely, same technique as SerZone.contains()) → pick the containing one
id_ser_zone → cached rates[] → match name (stripped "Tarifa " prefix) vs zone_type → id_ser_rate
```
No call to ElParking's zone/rate endpoints is needed for the common (62/71) case beyond the cached lookup; polygon parsing only happens for entries actually competing for the same zone_number within a town, not for every zone.

Alternative considered: always resolve the zone via ElParking's own polygons (ignore zone_number matching entirely, do point-in-polygon against every zone in the town). Rejected per explicit product decision — we already trust and maintain our own zone geometry; ElParking's polygons are used strictly as a tiebreaker, not the primary spatial source, keeping the two zone systems' roles distinct (ours: source of truth for "where is this vehicle"; ElParking's: source of truth for "what does ElParking call this place").

### 4. ElParking zone-mapping cache: infrastructure-only, `(city_code, provider)`-keyed, 30-day lazy refresh
New table `ser_ticket_provider_zone_mappings` — kept provider-agnostic in name (unlike `ElParkingClient`/`ElParkingSerTicketProvider`) since `provider` is already part of its composite key, not something to bake into the table name — storing, per `(city_code, provider)`: `id_ser_town`, the fetched zones (id, name, polygon_wkt) and their rates, and a `fetched_at` timestamp. A new repository (infrastructure-only — not a domain port, since its column vocabulary — `id_ser_town`, `id_ser_zone`, `id_ser_rate` — is ElParking-specific and must not leak past `SerTicketProviderPort`) reads this table; `ElParkingSerTicketProvider` checks `fetched_at` and re-fetches via `ElParkingClient` (using whichever session the current `create_ticket()` call already has) when the row is missing or older than 30 days.

Alternative considered: a scheduled background refresh job, mirroring `ingest_ser_zones.py`'s pattern. Rejected — that job would still need a valid ElParking session to call these endpoints (they're user-session-gated, not public), and no session is guaranteed to be available/fresh outside of an actual ticket-creation request. Lazy, request-triggered refresh sidesteps needing a dedicated "system" ElParking account.

### 5. `SerTicketProviderPort.create_ticket()` gains an explicit `location` parameter
```python
def create_ticket(
    self, session: SerProviderSession, vehicle: Vehicle, duration_minutes: int, location: GeoLocation
) -> ParkingTicket: ...
```
`CreateSerTicket.execute()` gains an optional `location: GeoLocation | None = None` parameter: when omitted, it resolves the vehicle's latest known location via the existing `GetLatestVehicleLocation` use case before calling `create_ticket()`; when provided (explicit HTTP override), it's passed through directly. The port itself always requires a resolved `GeoLocation` — pushing the "where do we get it from" decision to the use case keeps `create_ticket()` itself pure and, critically, means a future `VehicleLocationUpdated`-triggered call (which already has the event's lat/lng in hand) can pass it straight through without any extra lookup or signature change.

### 6. Vehicle-plate matching failure raises a typed exception; the use case publishes the event
`ElParkingSerTicketProvider.create_ticket()` calls `ElParkingClient.list_vehicles()` and matches by `vehicle.license_plate`; no match raises a new `SerProviderVehicleNotFoundError` (domain exception). `CreateSerTicket.execute()` catches it, publishes `VehicleNotPresentInSerTicketProvider(vehicle_id, user_id, provider)` via its injected `EventPublisher`, then re-raises. This follows the codebase's existing convention that use cases — not infrastructure adapters or repositories — publish domain events (`RecordVehicleLocation` is the only current example), keeping `ElParkingSerTicketProvider` itself event-publisher-free.

### 7. `ParkingTicket` gains `cost: float` and `end_date: datetime`
Populated directly from ElParking's response (`total_qty`, `end_date`). Plain `float` for cost (not a `Money` value object) — matches `ParkingTicket`'s existing "flat, opaque-where-necessary" shape, and no other entity in this codebase currently models money as a structured type; introducing one here would be a bigger, separate decision than this change needs to make.

### 8. New endpoint: `POST /parking/ser-tickets`
Added to the existing `presentation/api/routers/parking.py` (already hosts `GET /parking/ser-zone`). Body: `{"vehicle_id": UUID, "duration_minutes": int, "provider": str, "latitude": float | None, "longitude": float | None}`. Requires authentication; calls `CreateSerTicket.execute(user_id, vehicle_id, provider, duration_minutes, location=...)`, building the optional `GeoLocation` only when both lat/lng are supplied. Returns the created ticket (id, cost, end_date, provider_reference) on success.

This endpoint is intended as a manual/testing surface for this change, not the production trigger — see the idempotency Non-Goal above and the corresponding Risk below.

## Risks / Trade-offs

- **[Risk] Up to 6 sequential HTTP calls (vehicle list, town/zone/rate cache miss, steps, create) inside one `create_ticket()` invocation** → Mitigation: the 30-day cache eliminates the town/zone/rate calls on the common (cache-hit) path, leaving vehicle-list + steps + create as the steady-state cost — same order of magnitude as ElParking's own documented flow.
- **[Risk] Step 5's freshness window is provider-defined and unknown to us (`SystemParams::EXPIRE_REQUEST_TICKET`)** → Mitigation: `get_steps()` and the final `create_ticket` POST happen back-to-back with no cache or delay in between; if ElParking still rejects it as stale, that surfaces as `SerProviderApiError` like any other provider failure — no special-casing needed since we never persist or reuse `step_request`.
- **[Risk] The 9/71 duplicate-zone_number Madrid zones were found by manual inspection of one sampled dump, not exhaustively for every city ElParking covers** → Mitigation: the polygon-tiebreaker path handles arbitrarily many duplicates per zone_number for any city, not just Madrid's known 9 — the sampling only proved the tiebreaker is necessary, not that it's Madrid-specific.
- **[Trade-off] Cache can serve up to 30-day-stale zone/rate IDs if ElParking silently renames or restructures a zone** → Accepted; 30 days was an explicit product decision, and a stale `id_ser_zone` would surface as an ElParking-side rejection (`SerProviderApiError`) rather than silent corruption, since the zone/rate IDs are opaque strings ElParking itself validates.
- **[Risk] No idempotency protection on `POST /parking/ser-tickets`: a client that times out anywhere across the up-to-6-call chain and retries could cause a second real ElParking ticket to be created and charged** → Mitigation: accepted for now — this endpoint is a manual/testing surface (see Non-Goals), not the intended production trigger. The actual production path is the future `VehicleLocationUpdated`-based auto-creation, which is server-side event-driven with no HTTP client to time out or retry, so it does not inherit this risk. An idempotency-key contract change would be required before this endpoint (or any equivalent client-facing surface) is safe to expose to real callers.

## Migration Plan

1. Alembic migration adding `cost`/`end_date` columns to `parking_tickets` (nullable false, since every ticket created going forward will populate them).
2. Alembic migration creating the new ElParking zone-mapping cache table.
3. Deploy domain/application/infrastructure changes together with the new `POST /parking/ser-tickets` endpoint — this is the first production-facing use of `CreateSerTicket`, so it ships as one unit rather than incrementally.
4. Rollback: standard Alembic downgrades; the new cache table and new `parking_tickets` columns can be dropped without affecting any other capability.

## Open Questions

None outstanding — all prior open questions (location sourcing, cache strategy/TTL, vehicle-not-found handling, auth scheme, ticket entity fields) were resolved during exploration.
