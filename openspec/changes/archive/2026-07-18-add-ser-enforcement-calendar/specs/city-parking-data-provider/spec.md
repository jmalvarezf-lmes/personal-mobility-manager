## MODIFIED Requirements

### Requirement: Provider registry maps city code to provider instance
The system SHALL maintain a provider registry (a dict `city_code -> CityParkingDataProvider`) populated at application startup by querying the `cities` table (see the `city-registry` capability) for all registered city codes. For each `code` returned, if a matching provider implementation is registered in code, an instance SHALL be constructed and added to the registry; if no matching implementation exists for a `code` present in `cities`, the system SHALL log a warning and continue without that city. The `ENABLED_CITIES` environment variable and any hardcoded known-cities allowlist SHALL NOT be used to determine which cities are active — the `cities` table is the sole source of truth for which city codes are active.

#### Scenario: Default cities table activates Madrid only
- **WHEN** the `cities` table contains only the `code='madrid'` row
- **THEN** only `MadridSerStreetsProvider` is registered

#### Scenario: City code with no registered implementation is skipped with a warning
- **WHEN** the `cities` table contains a `code` with no matching provider implementation in code
- **THEN** the application logs a warning identifying the unimplemented code and starts normally without that city

#### Scenario: Multiple cities can be enabled simultaneously
- **WHEN** the `cities` table contains `madrid` and `barcelona` rows, and both have registered provider implementations
- **THEN** both providers are registered and scheduled independently

#### Scenario: ENABLED_CITIES has no effect
- **WHEN** the `ENABLED_CITIES` environment variable is set to any value, including one that excludes `madrid`
- **THEN** the provider registry is unaffected by it — only the `cities` table's rows determine which providers are built

#### Scenario: Per-source URL overrides remain unaffected
- **WHEN** `SER_ZONE_SHP_URL`, `MADRID_CALLEJERO_URL`, or `MADRID_BARRIOS_SHP_URL` env vars are set
- **THEN** the Madrid provider still uses those URLs instead of its defaults, since these configure a provider's own data sources, not which cities are active
