## ADDED Requirements

### Requirement: VehiclePullLocationPort defines the pull adapter contract
The system SHALL define `VehiclePullLocationPort` as an abstract base class with a single abstract method `fetch_location(vehicle_id, config_payload) -> VehicleLocation`. All pull-based brand adapters MUST implement this interface. Push-only brands SHALL NOT implement this interface.

#### Scenario: Toyota adapter satisfies the port
- **WHEN** `ToyotaLocationProvider` is instantiated
- **THEN** it is a valid instance of `VehiclePullLocationPort`
- **THEN** calling `fetch_location` with a valid Toyota config returns a `VehicleLocation` with `lat`, `lon`, `recorded_at`, `source="pull"`

#### Scenario: Push-only brand has no pull adapter
- **WHEN** `ENABLED_BRANDS` contains only `generic`
- **THEN** the `BrandRegistry` returns an empty list of pull providers
- **THEN** no pull scheduling occurs

---

### Requirement: BrandRegistry returns pull providers for enabled pull brands
The system SHALL provide a `BrandRegistry` that reads `ENABLED_BRANDS` and returns one `VehiclePullLocationPort` instance per pull-capable brand. Unknown brand codes SHALL be logged as warnings and skipped.

#### Scenario: Toyota provider instantiated when enabled
- **WHEN** `ENABLED_BRANDS=toyota`
- **THEN** `BrandRegistry.build_pull_providers()` returns a list containing one `ToyotaLocationProvider`

#### Scenario: Generic brand produces no pull provider
- **WHEN** `ENABLED_BRANDS=generic`
- **THEN** `BrandRegistry.build_pull_providers()` returns an empty list

#### Scenario: Unknown brand code is warned and skipped
- **WHEN** `ENABLED_BRANDS=toyota,unknown_brand`
- **THEN** the system logs a warning for `unknown_brand`
- **THEN** only the Toyota provider is returned

---

### Requirement: VehicleLocationScheduler polls pull brands on a configurable interval
The system SHALL run a `VehicleLocationScheduler` that, for each registered Toyota vehicle, decrypts its config, calls `ToyotaLocationProvider.fetch_location`, and delegates to `RecordVehicleLocation`. The poll interval SHALL be read from `VEHICLE_POLL_INTERVAL_MINUTES` (default: `5`).

#### Scenario: Scheduler fetches and records location for each Toyota vehicle
- **WHEN** the scheduler fires
- **THEN** for each vehicle with `brand=toyota`, the system fetches the location from the Toyota API
- **THEN** each fetched location is persisted via `RecordVehicleLocation` with `source="pull"`

#### Scenario: Scheduler tolerates per-vehicle failures
- **WHEN** the Toyota API returns an error for one vehicle
- **THEN** the error is logged for that vehicle
- **THEN** the scheduler continues processing remaining vehicles without aborting

#### Scenario: No pull scheduling when no pull brands are enabled
- **WHEN** `ENABLED_BRANDS=generic`
- **THEN** `VehicleLocationScheduler` starts but schedules no polling jobs

---

### Requirement: Toyota adapter authenticates via pytoyoda and returns GPS coords
The system SHALL implement `ToyotaLocationProvider` using the `pytoyoda` library. It SHALL authenticate with `username`, `password`, `locale` from the decrypted config, locate the vehicle by `vin`, and return `lat`, `lon`, and `recorded_at` from the vehicle's GPS data.

#### Scenario: Successful location fetch
- **WHEN** `ToyotaLocationProvider.fetch_location` is called with valid config
- **THEN** it returns a `VehicleLocation` with non-null `lat`, `lon`, and `recorded_at`

#### Scenario: VIN not found in Toyota account
- **WHEN** the Toyota account does not contain the configured VIN
- **THEN** `ToyotaLocationProvider.fetch_location` raises a domain exception
- **THEN** the scheduler logs the error and skips this vehicle

#### Scenario: Toyota API unavailable
- **WHEN** the pytoyoda call raises a network or authentication error
- **THEN** `ToyotaLocationProvider.fetch_location` raises a domain exception
- **THEN** the scheduler logs the error and continues with the next vehicle

---

### Requirement: ENCRYPTION_KEY required when toyota is enabled
The system SHALL raise a `RuntimeError` at startup if `toyota` is in `ENABLED_BRANDS` and `ENCRYPTION_KEY` is not set.

#### Scenario: Missing encryption key with Toyota enabled
- **WHEN** `ENABLED_BRANDS=toyota` and `ENCRYPTION_KEY` is not set
- **THEN** the application fails to start with a clear error message indicating `ENCRYPTION_KEY` is required
