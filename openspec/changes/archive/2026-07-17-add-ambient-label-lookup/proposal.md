## Why

Spain's DGT assigns every vehicle an environmental "distintivo ambiental" (A/no label, B, C, ECO, 0) that determines which low-emission zones (e.g. Madrid Distrito Centro/SER) it may enter. Users currently have no way to see this in the app even though we already track each vehicle's license plate. DGT publishes a public lookup form keyed by plate; a spike confirmed the result is server-rendered per-request (no JS/auth wall), so we can resolve it automatically instead of asking the user to type it in.

## What Changes

- Add a `VehicleAmbientLabel` lookup that queries DGT's public distintivo-ambiental form by license plate and parses the environmental label (A, B, C, ECO, 0) from the response HTML.
- Best-effort trigger the lookup when a vehicle is registered with a license plate present. Never blocks or fails registration if the lookup is slow or errors.
- Add a background scheduler that periodically drains the backlog of vehicles missing a resolved label (or whose last attempt failed/found nothing, past a cooldown), throttled to one lookup every 5 seconds to stay a polite, low-volume client of a government form not built for automated bulk use.
- Persist per-vehicle lookup state: the resolved label (when found), a status (`found` / `not_found` / `error`), and the timestamp of the last attempt — so a confirmed "no label" (category A) is never re-checked, while inconclusive results (not found / parse failure) retry later instead of being hammered every cycle.
- Surface the resolved label (or its absence) on vehicle read endpoints.
- Download and cache DGT's own sticker icon image for each label value (B/C/ECO/0) exactly once — shared across every vehicle with that label, not re-fetched per vehicle. Category A has no physical sticker, so no icon exists for it. Serve cached icons from our own API so the frontend never hotlinks DGT directly, and display the icon next to each vehicle's info in the vehicle list/detail views.

## Capabilities

### New Capabilities
- `ambient-label`: Looks up, stores, and exposes each vehicle's DGT environmental label (A/B/C/ECO/0), triggered at registration and backfilled by a throttled background scheduler for vehicles missing a confident result.

### Modified Capabilities
- `ui-i18n`: the new ambient-label UI component introduces hardcoded strings (label name, "no label" indication, icon alt text) that must be added to the translatable-components list and to both locale files, same as every other vehicle-facing component.

## Impact

- New domain concepts: `AmbientLabel` value object/enum, lookup status, a `VehicleAmbientLabelRepository` port, and a `vehicle_ambient_labels` table (Alembic migration).
- New infrastructure: an HTTP-based `DgtAmbientLabelProvider` (parses DGT's response HTML) and an `AmbientLabelScheduler` (mirrors the existing `VehicleLocationScheduler`/`ParkingIngestionScheduler` pattern, `BackgroundScheduler`-based, per-item try/except so one failing vehicle never blocks the rest).
- `RegisterVehicle` use case gains a best-effort call to trigger the lookup when a plate is supplied.
- `GET /vehicles`, `GET /vehicles/{id}`, and `POST /vehicles` responses gain ambient label fields — including the registration response, since the best-effort lookup runs synchronously before it's built, and clients shouldn't need a follow-up read to see a label resolved during the same request.
- New `ambient_label_icons` cache table (keyed by label value), a new `GET /ambient-labels/{label}/icon` endpoint, and frontend changes to `VehicleCard`/vehicle detail views to render the icon.
- External dependency: DGT's unofficial public form (`sede.dgt.gob.es`) — no auth, no documented SLA, markup can change without notice. Treated as an unreliable dependency: isolated behind a port, never allowed to raise into caller code paths, and failures degrade to "retry later" rather than surfacing errors to the user.
