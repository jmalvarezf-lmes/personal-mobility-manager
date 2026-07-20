## Context

`vehicle_locations` is already an append-only time series (one row per non-duplicate fix, see `record_vehicle_location.py`), but the only read paths are `get_latest` and `get_previous` — both single-row lookups used for the "last known position" card and for delta-threshold notification checks. No endpoint, use case, or repository method exists to page through multiple rows. The frontend has no pagination pattern anywhere yet (confirmed by full-repo search), so this change also sets the first convention for "load more" lists in this codebase.

The existing `GET /vehicles/{id}/location` endpoint and its `VehicleLocationResponse` schema (`vehicle_id`, `latitude`, `longitude`, `recorded_at`, `received_at`, `source`) stay untouched; history is an additive endpoint, not a replacement.

## Goals / Non-Goals

**Goals:**
- Let a user page through a single vehicle's location history (newest first), 5 at a time, from a modal opened off that vehicle's card.
- Reuse the existing ownership/auth model (session cookie, 401/403/404) already proven on `GET /vehicles/{id}/location`.
- Establish a simple, boring offset-pagination convention other list endpoints can copy later.

**Non-Goals:**
- No in-modal vehicle switcher — the modal is always scoped to the vehicle whose card triggered it.
- No changes to the shared multi-vehicle overview map (`VehicleMap` on `MyVehiclesPage`).
- No schema/migration changes — `vehicle_locations` and its index already support this access pattern.
- No live/streaming updates to an open history modal (out of scope; `VehicleLocationUpdated` stays a transient, in-process notification event, not wired into this view).

## Decisions

**Offset-based pagination, not cursor-based.** `vehicle_locations` is append-only and rows are never edited or deleted in normal operation, so the "items shift under you while paging" risk that usually motivates cursor pagination doesn't apply here. `GET /vehicles/{id}/locations?limit=5&offset=0` is simpler to implement and reason about than a `before=<timestamp>` cursor, and the user explicitly chose offset over cursor for this change.

**`has_more` via over-fetch, not `COUNT(*)`.** The repository requests `limit + 1` rows; if it gets back more than `limit`, `has_more=True` and the extra row is trimmed before returning. Avoids a second query per page and avoids the cost/complexity of a running total.

**Bounds:** `limit` defaults to 5, and is validated to `1 <= limit <= 50`; `offset >= 0`. Mirrors the input-validation posture already established for other endpoints (see `api-request-validation` capability) rather than trusting client-supplied values unchecked.

**New repository method, not a change to `get_latest`/`get_previous` semantics.** `list_history(vehicle_id, limit, offset) -> tuple[list[VehicleLocation], bool]` (items, has_more) is additive on the `VehicleLocationRepository` port. Existing callers of `get_latest`/`get_previous` are unaffected.

**New use case: `ListVehicleLocationHistory`.** Thin wrapper enforcing ownership (same pattern as `GetLatestVehicleLocation`) before delegating to the repository. Keeps the router handler declarative and testable in isolation.

**Frontend: one map, appended pins, not one map per page.** `VehicleLocationHistoryModal` holds an accumulated `locations` array (newest-first, matching API order) and an `offset`/`hasMore` pair. "Load more" fetches the next page and concatenates into the same array — same `MapContainer` instance re-renders with more markers/polyline points, it does not remount.

**Polyline drawn oldest → newest, list rendered newest → first.** The API returns newest-first (consistent with "last 5" framing and with the list UI). The map polyline is built from a **reversed** copy of the same array so the path reads as a chronological route r, not a scribble. This divergence (list order vs. polyline draw order) is deliberate and worth a code comment at the point where the array is reversed, since it's the one place list order and map order diverge.

**Newest-pin distinction.** The first item in the (newest-first) array gets the same car-style `DivIcon` already used for "current location" on the shared `VehicleMap`, for visual continuity. Older pins use a smaller, plain circle marker. Clicking any pin (new or old) opens a popup with that location's `recorded_at`.

**Modal follows the existing `AddVehicleModal`/`EditVehicleModal` convention.** State (`historyVehicle: VehicleListItem | null`) lives in `MyVehiclesPage`, set by a new callback prop from `VehicleCard` (e.g. `onViewHistory`), rendered as `{historyVehicle && <VehicleLocationHistoryModal vehicle={historyVehicle} onClose={...} />}`.

**Trigger is a dedicated button, not a clickable location line.** `VehicleCard`'s location line stays plain text; a new "View history" button is rendered next to it, shown only when `vehicle.location` is present. Revised after live use: a clickable text line reads as informational, not interactive — a button makes the affordance unambiguous.

**Direction arrows per polyline segment, no new dependency.** For each pair of chronologically consecutive points, compute the bearing between them and render a small rotated `DivIcon` marker at the segment's midpoint, rotated via CSS `transform: rotate(<bearing>deg)` pointing from the older point toward the newer one. Chosen over a plugin like `leaflet-polylinedecorator` to avoid adding a new frontend dependency for a small, self-contained bit of geometry (standard bearing formula: `atan2` of the delta longitude/latitude, adjusted to compass degrees). Revised after live use: a plain polyline with dots didn't communicate which end was "older" without opening popups on every pin — segment arrows make the route's direction legible at a glance.

## Risks / Trade-offs

- **[Risk]** Client can hammer `offset` with large values → mitigated by `limit` upper bound (50) and the fact that this is an authenticated, owner-scoped, read-only query against an indexed column (`ix_vehicle_locations_vehicle_recorded`); no unbounded scan risk.
- **[Risk]** Divergence between list order (newest-first) and polyline draw order (oldest-first) could confuse a future maintainer reading the component → mitigated by calling it out explicitly in this design and with a short inline comment at the reversal point.
- **[Trade-off]** Offset pagination can, in theory, skip/repeat a row if a new location is recorded between page loads while the modal is open (row inserted "above" the current offset window shifts everything down by one). Accepted: this is a manual "load more" click, not a live feed, and the practical odds of a same-second insert are low for this app's location-update cadence (vehicle polling, not sub-second telemetry).
- **[Risk, found in 4R review]** `list_history` originally ordered by `recorded_at DESC` alone. Duplicate `recorded_at` values across rows are a documented, real occurrence for this table (see this repository's own `get_previous`, which sorts on `received_at` for exactly this reason) — without a secondary sort key, OFFSET/LIMIT pagination across separate page-load queries isn't guaranteed stable when a tie sits at a page boundary, and could duplicate or skip a row on "load more." → Mitigated: added `received_at` as a secondary `ORDER BY` key.
- **[Risk, found in 4R review]** The new `GET /vehicles/{id}/locations` endpoint had no rate limiter, unlike the POST/PUT endpoints in the same router. → Mitigated: added the same `@limiter.limit(...)` convention used elsewhere in this router. `offset`'s upper bound was left unbounded by explicit choice — it's owner-scoped, not cross-tenant, and Postgres OFFSET cost against a single owner's own (bounded, personal-scale) history is accepted as-is.

## Migration Plan

Additive only — new repository method, new use case, new router endpoint, new frontend component. No existing endpoint, schema, or component behavior changes. No data migration. No rollback concerns beyond a normal revert.
