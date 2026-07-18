### Requirement: holidays database table
The system SHALL maintain a `holidays` table in PostgreSQL with columns: `id` (serial PK), `city_code` (text, references `cities.code`), `date` (date), `name` (text), `source` (text, `'ical_national'` or `'manual'`), with a `UNIQUE (city_code, date, source)` constraint. Rows with `source='manual'` SHALL be entered by hand (e.g. regional/local holidays not covered by the national calendar feed) and SHALL NEVER be inserted, updated, or deleted by the automated refresh job.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `holidays` table is created if it does not already exist, with no seed rows

#### Scenario: National and manual holidays coexist on the same date
- **WHEN** a `city_code` has both a `source='ical_national'` row and a `source='manual'` row for the same `date`
- **THEN** both rows are accepted, since the unique constraint is scoped by `source` as well as `date`

#### Scenario: Duplicate refresh insert is idempotent
- **WHEN** the refresh job attempts to insert a `source='ical_national'` row for a `(city_code, date)` pair that already has one
- **THEN** the existing row's `name` is updated in place (upsert), not duplicated

---

### Requirement: PublicHolidayProvider port and Google Calendar iCal implementation
The system SHALL define a `PublicHolidayProvider` port in the domain layer with a method returning the raw fetched `.ics` calendar text for Spain's national/regional calendar feed (not pre-parsed into holiday records — see the filtering requirement below for why parsing is deferred and city-specific). The concrete implementation SHALL fetch the feed (default `https://calendar.google.com/calendar/ical/es.spain%23holiday%40group.v.calendar.google.com/public/basic.ics`, overridable via env var), enforce a hostname allowlist restricting requests to `calendar.google.com`, and perform exactly one HTTP fetch per refresh run regardless of how many cities are configured (see the refresh requirement below).

#### Scenario: Successful fetch
- **WHEN** the feed URL is reachable and returns a valid `.ics` payload
- **THEN** the provider returns the raw `.ics` text unmodified

#### Scenario: Fetch failure does not raise from within the provider silently
- **WHEN** the HTTP request returns a non-2xx status or a network error occurs
- **THEN** the provider raises an error (matching the fail-loud convention of other providers), which the calling use case/scheduler catches, logs, and continues without modifying existing `holidays` rows

#### Scenario: Hostname allowlist enforced
- **WHEN** the provider is constructed with a URL whose host is not `calendar.google.com`
- **THEN** construction raises an error rather than allowing the fetch

#### Scenario: Configurable URL
- **WHEN** the holiday calendar URL env var is set
- **THEN** the provider uses that URL instead of the default

---

### Requirement: Filter calendar events to genuine, city-applicable public holidays only
The upstream Google Calendar feed contains both real public holidays and non-holiday "celebrations" (e.g. Carnival, Father's Day, Easter Sunday, New Year's Eve, DST changes) that must NOT be treated as holidays. The system SHALL classify each `VEVENT` using its `DESCRIPTION` field, evaluated per target city:
- If `DESCRIPTION` is exactly `"Día festivo"`, the event IS a public holiday, applicable to every city (a national holiday).
- Else if `DESCRIPTION` begins with `"Celebración en "` followed by a comma-separated list of Spanish region/city names (e.g. `"Celebración en Andalucía, Aragón, ..., Madrid, Murcia, ..."`), the event IS a public holiday only for a target city whose display name (its `city_code` capitalized) appears as an exact entry in that list — this covers holidays the feed labels as regional for a specific year (e.g. a Labour Day or Christmas instance shown as `"(festivo regional)"`) rather than the generic `"Día festivo"` label.
- Else (a generic `"Celebración"` description with no region list, or a `"Celebración en <regions>"` list that does not include the target city), the event is NOT a public holiday for that city and SHALL be excluded — regardless of how prominent-sounding its `SUMMARY` is (e.g. `"Navidad (festivo regional)"` for a region list that excludes the target city is still excluded for that city).

This filtering is inherently per-city: the same raw feed can yield different holiday sets for different cities (a regional entry naming Madrid but not Barcelona means Madrid gets that date as a holiday, Barcelona does not).

#### Scenario: National holiday is kept for every city
- **WHEN** a `VEVENT` has `DESCRIPTION` exactly `"Día festivo"`
- **THEN** it is included as a holiday for every city the refresh is run for

#### Scenario: Generic celebration with no region list is excluded
- **WHEN** a `VEVENT`'s `DESCRIPTION` is `"Celebración\nPara ocultar las celebraciones, ve a Configuración en Google Calendar > Festivos en España"` (no `"en <regions>"` clause) — e.g. Carnival, Father's Day, Easter Sunday, a DST change
- **THEN** it is excluded from every city's holiday set

#### Scenario: Regional entry naming the target city is kept for that city
- **WHEN** a `VEVENT`'s `DESCRIPTION` is `"Celebración en Andalucía, Aragón, ..., Madrid, Murcia, ...\nPara ocultar..."` and the target city's `city_code` is `"madrid"`
- **THEN** it is included as a holiday for that city, since `"Madrid"` appears in the region list

#### Scenario: Regional entry not naming the target city is excluded for that city
- **WHEN** a `VEVENT`'s `DESCRIPTION` lists regions that do not include the target city's capitalized `city_code`
- **THEN** it is excluded from that city's holiday set, even though it may be included for a different city whose name does appear in the list

#### Scenario: Region-list matching is exact, not substring
- **WHEN** matching the target city's capitalized `city_code` against the comma-separated region list
- **THEN** matching compares each trimmed list entry for exact equality, not a substring/`in` check against the raw description text, to avoid false positives from region names that share a prefix or contain another name

---

### Requirement: Refresh applies fetched, city-filtered holidays per enabled city without touching manual rows
The system SHALL implement a use case that performs exactly one raw calendar fetch per run, then for each enabled city independently filters that raw calendar (per the filtering requirement above) and upserts the resulting city-specific holiday records into `holidays` with `source='ical_national'` (matching on `(city_code, date, source)`). It SHALL NOT delete or modify any `source='manual'` row.

#### Scenario: Refresh inserts one row per enabled city per applicable holiday
- **WHEN** the refresh runs with a raw calendar containing 2 events whose `DESCRIPTION` is exactly `"Día festivo"` and 1 enabled city
- **THEN** 2 rows are inserted into `holidays` for that city, each with `source='ical_national'`

#### Scenario: Two cities can receive different holiday sets from the same fetch
- **WHEN** the refresh runs for two enabled cities and the raw calendar contains one regional event naming only the first city
- **THEN** the first city's `holidays` rows include that date, and the second city's `holidays` rows do not, even though both cities were refreshed from the same single fetch

#### Scenario: Refresh never touches manual rows
- **WHEN** the refresh runs and `holidays` already contains `source='manual'` rows for the same city
- **THEN** those rows are left completely unchanged (not read, updated, or deleted) by the refresh

---

### Requirement: Scheduled refresh with startup-conditional immediate fetch
The system SHALL run the holiday refresh on a configurable interval (default: every 6 months). At application startup, the scheduler SHALL trigger an immediate refresh run for a given enabled city only if that city currently has zero `source='ical_national'` rows in `holidays`; if at least one such row exists, the scheduler SHALL wait for the next regularly scheduled interval instead of firing immediately.

#### Scenario: Empty holiday data triggers immediate fetch on startup
- **WHEN** the application starts and an enabled city has zero `source='ical_national'` rows in `holidays`
- **THEN** the refresh job for that city runs immediately, before waiting for the configured interval

#### Scenario: Existing holiday data skips the immediate fetch on startup
- **WHEN** the application starts and an enabled city already has at least one `source='ical_national'` row in `holidays`
- **THEN** the refresh job for that city does not run immediately; it waits for the next scheduled interval tick

#### Scenario: Configurable interval
- **WHEN** the refresh interval env var is set to a positive integer number of hours
- **THEN** the scheduler uses that interval instead of the 6-month default

#### Scenario: Provider failure does not stop other cities or crash the scheduler
- **WHEN** the fetch fails for one city during a scheduled or startup-conditional run
- **THEN** the scheduler logs the failure and continues processing other enabled cities, and the application does not crash
