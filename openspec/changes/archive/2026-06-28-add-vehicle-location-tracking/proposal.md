## Why

The platform knows about parking zones but has no concept of where a vehicle actually is. Without vehicle location, there is no way to determine whether a user's car is inside a SER zone, trigger alerts, or surface actionable mobility insights. This change introduces the foundational vehicle location layer — supporting both active polling (Toyota via pytoyoda) and passive push (any device that can POST a GPS coordinate).

## What Changes

- Introduce `Brand` enum (`toyota`, `generic`) as a domain value object; `Vehicle.brand` is typed to this enum.
- Add `Vehicle` entity with `id`, `brand`, `display_name`, `vin`.
- Add `VehicleConfig` infrastructure concept: per-vehicle configuration stored in a new DB table. Toyota credentials (username, password, locale, vin) are stored AES-encrypted. Generic `location_token` is stored in cleartext (not user-identifiable).
- Add `VehicleLocation` entity capturing `vehicle_id`, `lat`, `lon`, `recorded_at` (source clock), `received_at` (system clock), `source` (`pull` | `push`). Full history is retained.
- Add `VehiclePullLocationPort` — abstract interface for pull-based location adapters.
- Add `ToyotaLocationProvider` implementing `VehiclePullLocationPort` via pytoyoda.
- Add `GenericLocationProvider` — marker class for push-only brands (no pull method).
- Add `BrandRegistry` (mirrors `CityProviderRegistry`) — reads `ENABLED_BRANDS` env var (default: `generic`), returns active pull providers for the scheduler.
- Add `VehicleLocationScheduler` — polls pull-brand vehicles at a configurable interval.
- Add `RecordVehicleLocation` use case — shared entry point for both pull and push paths.
- Add REST endpoints:
  - `POST /vehicles` — register a vehicle; returns `location_token` for generic brand.
  - `GET /vehicles/{id}/location` — latest known location for a vehicle.
  - `POST /vehicles/{token}/location` — push endpoint for generic; token resolves to vehicle.
- Add `ENABLED_BRANDS` and `ENCRYPTION_KEY` env vars; `VEHICLE_POLL_INTERVAL_MINUTES` for scheduler cadence.

## Capabilities

### New Capabilities

- `vehicle-registry`: Register and retrieve vehicles with brand-specific configuration stored securely.
- `vehicle-location-pull`: Pull-based location ingestion via brand adapters (Toyota → pytoyoda).
- `vehicle-location-push`: Push-based location ingestion via per-vehicle token endpoint (generic brand).
- `vehicle-location-query`: Query the latest known location of a registered vehicle.

### Modified Capabilities

*(none — no existing spec-level requirements change)*

## Impact

- **New DB tables**: `vehicles`, `vehicle_configs`, `vehicle_locations` — requires schema migration.
- **New dependency**: `pytoyoda` (Toyota adapter); `cryptography` (Fernet AES encryption for Toyota credentials).
- **New env vars**: `ENABLED_BRANDS` (default `generic`), `ENCRYPTION_KEY` (required when toyota is enabled), `VEHICLE_POLL_INTERVAL_MINUTES` (default `5`).
- **API surface**: Three new endpoints under `/vehicles`.
- **Existing scheduler pattern**: New `VehicleLocationScheduler` mirrors `ParkingIngestionScheduler` — both start/stop in FastAPI lifespan.
- **`Vehicle` entity**: Currently an empty stub — this change fills it in (non-breaking, no existing callers).
- **`VehicleProviderPort`**: Currently an empty stub — replaced by the more specific `VehiclePullLocationPort` (non-breaking).
