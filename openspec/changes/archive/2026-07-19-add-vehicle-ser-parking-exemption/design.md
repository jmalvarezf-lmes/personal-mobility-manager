## Context

`DetermineSerTicketRequirement.execute(zone)` decides whether a SER ticket is currently required for a vehicle's location. Today it only consults the injected `SerEnforcementSchedule` (weekday hours, calendar exceptions, holidays). Its own docstring — and the `ser-ticket-requirement` spec — reserve "a resident permit held for that specific zone" as a future factor, and assert it will arrive "as an injected constructor dependency... without changing `execute()`'s signature or any caller's call site."

That assertion does not hold for what's being built here: an exemption is inherently per-vehicle data. No constructor-injected dependency can answer "is *this* vehicle exempt" without `execute()` being told which vehicle is being asked about. This design accepts that `execute()`'s signature must grow, and treats the old docstring/spec text as superseded rather than binding.

The only current caller of `DetermineSerTicketRequirement` is `SerTicketTriggerHandler` (the notification trigger on `VehicleLocationUpdated`). There is no separate "check if I need a ticket" API endpoint today, and no automatic ticket creation — this stays true.

`ZoneArea` (`ser_zone_areas`, PK `(city_code, zone_number)`) already carries a `neighbourhood` display name per zone_number, populated from Madrid's Barrios shapefile via `add-ser-zone-frontiers`. It is explicitly documented as "presentation-only" and never used in containment/liability logic today (`SerZone.contains()`). This change keeps that boundary: the exemption's persisted identity is `(city_code, zone_number)`, matching exactly what `FindContainingSerZone` already resolves; `neighbourhood` is read only to label options in the picker UI, never compared at check time.

Only Madrid exists in the `cities` table today (single seed row), and `GET /parking/ser-zones` independently hardcodes `_SUPPORTED_CITIES = {"madrid"}` at the router level. This change removes that hardcoding so the new city picker (and the existing endpoint) reflect whatever `cities` actually contains.

## Goals / Non-Goals

**Goals:**
- Let a vehicle owner record that they've already paid to park in one specific SER zone, identified by `(city_code, zone_number)`.
- Suppress the `ser_zone_ticket_required` notification when the vehicle's current zone matches its stored exemption.
- Make the exemption picker's city step live (no hardcoded city), consistent with the multi-city foundation already laid by `add-ser-enforcement-calendar`.

**Non-Goals:**
- Automatic SER ticket creation/cancellation — out of scope, as it is for the rest of this capability.
- Home-proximity-based exemption — still an unevaluated seam, unaffected by this change.
- Multiple simultaneous exemptions per vehicle — one vehicle, one exempt zone, matching the real-world resident-permit model (a permit is issued for one registered zone).
- Any behavior change to `SerZone.contains()` or bulk zone/frontier rendering beyond the city-validation fix described below.

## Decisions

### D1: Exemption identity is `(city_code, zone_number)`, not neighbourhood text
**Chosen**: `vehicle_ser_parking_exemptions` stores `city_code` + `zone_number`, with a composite FK to `ser_zone_areas(city_code, zone_number)`.
**Why**: `zone_number` is exactly what `SerZone` (and thus `FindContainingSerZone`'s result) carries — the runtime check becomes a direct tuple comparison, no secondary neighbourhood lookup or string matching needed. `neighbourhood` names are not unique/stable identifiers (`ser-zone-frontier`'s design.md notes they're presentation-only and can duplicate across zone_numbers within a barrio); using text as the join key would be fragile and would need re-deriving the neighbourhood at check time for every event.
**Alternative considered**: Store the neighbourhood name directly and match "vehicle's current zone's neighbourhood == stored neighbourhood," exempting the whole barrio at once. Rejected: neighbourhood is documented as presentation-only, adds a mandatory `get_zone_area` lookup on every location event, and silently exempts more zones than the one the owner actually selected.

### D2: Composite FK to `ser_zone_areas`, not `ser_zones`
**Chosen**: FK targets `ser_zone_areas(city_code, zone_number)`.
**Why**: This guarantees any zone an owner can select already has a resolvable neighbourhood label for the picker (by construction — the picker only offers zone_numbers present in `GET /parking/ser-zones`'s `frontiers[]`). It also matches `ser-zone-frontier`'s documented grain: `(city_code, zone_number)`, independent of `zone_type` — the same grain `FindContainingSerZone`'s result needs to match against, since a zone_number can have multiple `zone_type` rows in `ser_zones` but exactly one `ser_zone_areas` row.
**Alternative considered**: FK to `ser_zones(city_code, zone_number, zone_type)`. Rejected: would force the picker to also choose a `zone_type`, which is irrelevant to the exemption (a resident permit is not scoped to a colour) and isn't information the picker's neighbourhood-labeled UI is set up to surface cleanly.

### D3: One exemption row per vehicle (unique `vehicle_id`)
**Chosen**: `vehicle_id` is the primary key of `vehicle_ser_parking_exemptions` (not part of a composite key with city/zone). Setting a new exemption replaces the existing row (upsert); there is no history.
**Why**: Matches the real-world model (one resident permit per vehicle) and keeps the picker/API a simple "pick one, replace, or clear" flow rather than a list-management UI.

### D4: `DetermineSerTicketRequirement.execute()` signature changes; enforcement check stays first
**Chosen**: `execute(self, zone: SerZone | None, vehicle_id: UUID) -> bool`. Order of checks: `zone is None` → `False`; then enforcement schedule inactive → `False`; then exemption match → `False`; otherwise `True`.
**Why**: Enforcement-inactive should short-circuit before touching the exemption repository at all — if no ticket would ever be required (e.g. it's a Sunday), there's no need to look up the vehicle's exemption. This preserves today's cheapest-check-first ordering and only adds the new repository call on the path that would otherwise return `True`.
**Alternative considered** (and explicitly ruled out during exploration): add the exemption check as a new gate inside `SerTicketTriggerHandler` instead, leaving `DetermineSerTicketRequirement`'s signature untouched. Rejected because `DetermineSerTicketRequirement` is the single, designated "is a ticket needed" authority — a future ticket-creation flow reusing it would otherwise miss the exemption. The old "no signature change" seam in its docstring/spec is corrected as part of this change (see Context).

### D5: New REST sub-resource under `/vehicles/{id}`, not folded into `PUT /vehicles/{id}`
**Chosen**: `GET/POST/DELETE /vehicles/{id}/ser-parking-exemptions` (plural path, singleton resource under it — no id in the path since at most one row exists per vehicle). `POST` upserts (create or replace); `DELETE` clears.
**Why**: `UpdateVehicleRequest` is a brand-discriminated union (Toyota/Generic) purely about vendor config and identity fields; the exemption has nothing to do with vendor branding and would awkwardly need to be threaded through both union variants. A dedicated sub-resource follows the existing pattern of `/vehicles/{id}/location` and reuses the same ownership-check shape already used throughout `vehicles.py` (`if vehicle.user_id != current_user.id: raise HTTPException(403, ...)`).

### D6: New `GET /cities` endpoint; `zones.py`'s hardcoded city set is removed
**Chosen**: Add `GET /cities` returning all `cities` rows (`code`, `name`). Replace `zones.py`'s `_SUPPORTED_CITIES = {"madrid"}` literal with a live check against the `cities` table (via the same `cities` read path).
**Why**: The picker's first step ("select a city") must reflect real data, not a hardcoded value the user explicitly rejected. Since `GET /parking/ser-zones` already needs the same live city validation to be useful with more than one city, fixing its pre-existing hardcoding here keeps the whole city-scoping story consistent in one change rather than leaving a second hardcoded city set beside the new one.
**Alternative considered**: Leave `zones.py` as-is and only make the new endpoints live. Rejected per explicit instruction — the new picker would otherwise sit right next to unrelated hardcoded behavior that contradicts it.

### D7: GET /parking/ser-zones gains dedicated city-scoped repository queries
**Chosen**: Add `SerZoneRepository.list_zones_for_city(city_code)` and `list_zone_areas_for_city(city_code)`. `zones.py` calls these instead of the existing unscoped `list_all()`/`list_zone_areas()`.
**Why**: Investigation during this change surfaced that `list_all()`/`list_zone_areas()` (and thus `GET /parking/ser-zones`) are **not actually city-scoped today** — the router's `city` query param is only used for the `_SUPPORTED_CITIES` check and echoed into the response's `city` field; the underlying SQL has no `WHERE city_code = ...` clause (`list_zone_areas()`'s own docstring says "across all cities"). This is invisible today only because Madrid is the sole seeded city. The new city-then-zone picker (D6) depends on `?city=<selected>` actually returning only that city's `frontiers`, so this latent gap must be closed as part of this change, not left to coincide correctly.
**Alternative considered**: Filter `list_all()`/`list_zone_areas()`'s results in Python inside `zones.py` after fetching everything. Rejected: wasteful once a second city has real data (fetches and reprojects zones that get thrown away), and `list_all()` must stay unscoped anyway for `find_containing()`/`find_nearest()`, which don't know the city in advance — so a separate scoped method is cleaner than overloading the existing one with an optional filter parameter.

### D8: No neighbourhood resolution at check time
Following from D1, `DetermineSerTicketRequirement` never calls `SerZoneRepository.get_zone_area()`. This also sidesteps the "zone_number has no matching Barrios record" edge case entirely for the check path — it only matters for what the picker can offer, not for whether an already-stored exemption applies.

## Risks / Trade-offs

- **[Risk]** A vehicle's exemption becomes stale if `ser_zone_areas` data is re-ingested and a `zone_number`'s neighbourhood mapping changes (e.g. Barrios shapefile updates). → **Mitigation**: The FK is on `(city_code, zone_number)`, not on the neighbourhood name, so the stored exemption is unaffected by neighbourhood re-labeling; only a `zone_number` actually disappearing from `ser_zone_areas` would orphan a row, and the FK constraint prevents that from happening silently (the delete would need to cascade or be blocked — see Migration Plan).
- **[Risk]** Deleting a vehicle should not leave an orphaned exemption row. → **Mitigation**: `vehicle_id` FK to `vehicles.id` with `ON DELETE CASCADE`, consistent with how `vehicle_configs` is scoped to its vehicle.
- **[Trade-off]** One exemption per vehicle means an owner with two legitimate paid zones (e.g. moved neighbourhoods mid-year but kept an old permit active) can't represent both. Accepted per D3 — real resident permits are 1:1 with a registered zone, and the added complexity of a list UI isn't justified today.

## Migration Plan

1. Add `vehicle_ser_parking_exemptions` table via Alembic migration: `vehicle_id UUID PK REFERENCES vehicles(id) ON DELETE CASCADE`, `city_code TEXT NOT NULL`, `zone_number VARCHAR(10) NOT NULL`, composite FK `(city_code, zone_number) REFERENCES ser_zone_areas(city_code, zone_number)`, `updated_at TIMESTAMPTZ NOT NULL`.
2. Ship backend changes (entity, port, Postgres repository, updated `DetermineSerTicketRequirement`, updated `SerTicketTriggerHandler` call site, new router, `zones.py` city-validation fix, DI wiring in `app.py`) together — `DetermineSerTicketRequirement.execute()`'s signature change and its one caller must land in the same deploy.
3. Ship frontend picker after the backend endpoints are live.
4. Rollback: downgrade migration drops the new table; no other schema is touched. No data migration/backfill is needed since this is a net-new, opt-in feature (no existing rows to reconcile).

## Open Questions

None outstanding — cardinality, check placement, storage grain, REST shape, and city-hardcoding scope were all resolved during exploration. The `GET /parking/ser-zones` city-filtering gap (D7) was found and resolved while writing this design.
