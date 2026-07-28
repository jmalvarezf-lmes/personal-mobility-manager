## Context

`ParkingTicket` (`src/mobility_manager/domain/entities/parking_ticket.py`) already carries `city_code`/`zone_number` but never persisted the coordinates it was created at, even though `CreateSerTicket.execute` already resolves a `GeoLocation` (either explicit or the vehicle's latest known location) before calling the provider. Nothing on the entity or table distinguishes a ticket created by `SerTicketCreationTriggerHandler` (automatic, on zone transition) from one created via the manual `POST /parking/ser-tickets` endpoint — both go through the same `CreateSerTicket.execute` call. There is also no endpoint to list a vehicle's tickets at all; only `find_all_active_for_vehicle` exists, for the idempotency check in `DetermineSerTicketRequirement`.

The frontend already has a working precedent for "per-vehicle history in a modal with a map": `VehicleLocationHistoryModal.tsx` + the "View history" button on `VehicleCard.tsx`, gated on `vehicle.location` being non-null (no extra fetch to decide visibility). This change follows that same shape for SER tickets.

## Goals / Non-Goals

**Goals:**
- Persist enough data on `ParkingTicket` (coordinates + creation provenance) to support listing and mapping every ticket, and labeling each as auto-created or manual.
- Expose a paginated, vehicle-scoped ticket list over HTTP, covering all tickets regardless of how they were created.
- Gate a new "View SER tickets" button the same zero-extra-fetch way `location` already gates "View history" — visible whenever the vehicle has any ticket at all.
- Render each ticket on a single-marker map (no path, no arrows) plus its start/end dates, city, zone, and an auto/manual label — fully i18n'd.

**Non-Goals:**
- Backfilling `auto_created`, `latitude`, or `longitude` for tickets created before this change — those rows simply show with an unlabeled/unknown provenance and no map marker, rather than being excluded (same precedent as `city_code`/`zone_number` being `None` for pre-existing rows, see `ser-ticket-provider`'s `ParkingTicket` requirement).
- Drawing the SER zone polygon on the map — a single marker is sufficient; zone/city are shown as text.
- Editing or cancelling tickets from this view — read-only.

## Decisions

**D1 — `auto_created` as a nullable boolean column, not a `source` string/enum.**
There are only ever two ticket-creation paths — the manual `POST /parking/ser-tickets` endpoint and `SerTicketCreationTriggerHandler`'s event-driven path — and no third is anticipated (a bulk-import or similar would be a different, larger change in its own right). A boolean says exactly that: "was this auto-created, yes or no," with no closed-vocabulary string to keep in sync across layers. Nullable (not defaulted to `false`) so pre-existing rows read back as `None` ("unknown provenance"), matching the same precedent already used for `city_code`/`zone_number`/`latitude`/`longitude`. Alternative considered: a `source: str` enum (`"manual"`/`"auto"`) — rejected as over-general for a fact with exactly two known states and no planned third.

**D2 — `CreateSerTicket.execute` gains an `auto_created: bool = False` parameter (default preserves the existing manual endpoint's behavior unchanged); `SerTicketCreationTriggerHandler` passes `auto_created=True`.**
Keeps `POST /parking/ser-tickets` a no-op change — no caller update needed for the default case. Alternative considered: infer the flag from *how* `execute` is invoked (e.g. a thread-local flag) — rejected as implicit and harder to test.

**D3 — Coordinates are persisted from the same `GeoLocation` already resolved inside `CreateSerTicket.execute` (the `location` parameter, or the fallback latest-known-location lookup) — no new location lookup is introduced.**
This is exactly the coordinate value already passed to `create_ticket(session, vehicle, duration_minutes, location)`; we're only adding "and also store it on the entity/row," not adding a new resolution path.

**D4 — New endpoint is `GET /vehicles/{vehicle_id}/ser-tickets`, not `GET /parking/ser-tickets?vehicle_id=`.**
Keeps vehicle-scoped resources under `/vehicles/{id}/...`, consistent with the existing `/vehicles/{id}/locations`, and reuses `require_owned_vehicle` for ownership checks the same way. Pagination shape (`limit`/`offset` query params, `has_more` in response) copies `list_location_history` exactly. The endpoint returns every ticket for the vehicle — no `auto_created` filter is applied server-side; each item simply carries its own `auto_created` value so the client can label it.

**D5 — City display name resolution happens server-side, in the new list use case, via a lookup against the existing `cities` table/repository — not client-side.**
The frontend has no existing cities lookup; adding one client-side would duplicate a mapping the backend already owns (`CityResponse` via `cities.py`). Response includes both `city_code` and the resolved `city_name` so the frontend never needs to guess.

**D6 — `has_ser_tickets` is computed via an `EXISTS` query per vehicle inside the existing `GET /vehicles` list, not via a separate count endpoint.**
Matches D-equivalent precedent: `location` is already inlined into the same response for the same reason (avoid N+1 round trips from the vehicle list). The query is a cheap existence check (`vehicle_id = ...`, no `auto_created` filter — the button now gates on "any ticket exists," not "any auto-created ticket exists"), not a full ticket fetch.

**D7 — The new modal is a new, separate component (`VehicleSerTicketHistoryModal.tsx`), not a parameterized variant of `VehicleLocationHistoryModal.tsx`.**
The two modals share map scaffolding (`MapContainer`/`TileLayer`/container sizing/marker styling) but differ enough in data shape (list of discrete tickets, each independently centered, vs. one connected chronological path) that forcing one component to handle both would need more conditional branching than duplication costs. No new shared "base map" abstraction is introduced by this change — that refactor is out of scope here and can be revisited if a third map-modal appears.

**D8 — Each ticket row shows a small auto/manual label driven directly by `auto_created`; a ticket with `auto_created=null` (pre-existing row) shows a distinct "unknown" label rather than defaulting to either.**
Keeps the three actual states (`true`/`false`/`null`) visibly distinct instead of collapsing `null` into "manual," which would misrepresent provenance that's genuinely unknown. A ticket with no stored coordinates (also only possible for pre-existing rows) shows the details list but omits the map rather than rendering a marker at `(0, 0)` or hiding the entire entry.

## Risks / Trade-offs

- **[Risk] Pre-existing tickets will show `auto_created=null` ("unknown") forever, even if some were in fact auto-created before this field existed.** → Mitigation: explicitly a non-goal (see above); acceptable since there is no reliable way to distinguish old rows' provenance today, and the same precedent already exists for `city_code`/`zone_number`.
- **[Risk] Adding an `auto_created` parameter to `CreateSerTicket.execute` is a shared-use-case signature change touching both the manual HTTP path and the automatic trigger handler.** → Mitigation: default value keeps the manual path's call sites unchanged; only the trigger handler's call site needs a one-line update.
- **[Trade-off] Duplicating map scaffolding into a second component (D7) instead of extracting a shared base.** → Accepted for now to avoid a premature abstraction over a two-instance pattern; revisit if a third map-based modal is added later.
- **[Risk] Pre-existing tickets with no stored coordinates will render in the list with no map, which could read as a rendering bug rather than a known data gap.** → Mitigation: D8's explicit "omit map, keep details" behavior, plus a clear per-row state rather than a blank space.

## Migration Plan

1. Alembic migration: add `latitude FLOAT NULL`, `longitude FLOAT NULL`, `auto_created BOOLEAN NULL` to `parking_tickets`. All nullable — existing rows are unaffected and simply read back as `None`/`null`.
2. Deploy backend: `ParkingTicket` entity, `CreateSerTicket.execute`, `SerTicketCreationTriggerHandler`, new list use case + repository method, new router endpoint, `GET /vehicles` schema addition.
3. Deploy frontend: new API function/type, new button + modal, new i18n keys (both locales in the same commit — no partial-locale rollout).
4. No rollback complexity beyond the standard migration-down path (drop the three columns); no data backfill is performed in either direction.

## Open Questions

None outstanding — all prior ambiguities (button-visibility mechanism, city-name resolution, coordinate availability at ticket-creation time, ticket scope) were resolved during exploration.
