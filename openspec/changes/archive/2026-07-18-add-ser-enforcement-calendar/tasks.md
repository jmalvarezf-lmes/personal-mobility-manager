## 1. Database migrations

- [x] 1.1 Migration: create `cities` table, seed `code='madrid'` row
- [x] 1.2 Migration: create `ser_timetable_weekday_hours` + `ser_timetable_exception` tables, seed Madrid's 7 weekday rows and 3 exception rows (August, Dec 24, Dec 31), FK to `cities`
- [x] 1.3 Migration: create `holidays` table (schema only, `UNIQUE (city_code, date, source)`, no seed rows), FK to `cities`
- [x] 1.4 Migration: add `city_code` to `ser_zones`, `ser_zone_streets`, `ser_zone_areas`; backfill existing rows to `'madrid'`; widen `ser_zones` unique constraint to `(city_code, zone_number, zone_type)`, `ser_zone_areas` primary key to `(city_code, zone_number)`, `ser_zone_streets` index to `(city_code, zone_number, zone_type)`
- [x] 1.5 Update `infrastructure/orm/tables.py` to mirror all new/changed table definitions (shared source of truth for alembic autogenerate)

## 2. Domain layer

- [x] 2.1 Add `city_code: str` field to `SerZone` domain entity
- [x] 2.2 Add `city_code: str` field to `ZoneArea` domain value object
- [x] 2.3 Update `SerZoneRepository` port: `get_street_names(city_code, zone_number, zone_type)`, `get_zone_area(city_code, zone_number)`
- [x] 2.4 Add new domain port `SerEnforcementSchedule` (or equivalent) with `is_active_now(city_code: str) -> bool`
- [x] 2.5 Add new domain port `PublicHolidayProvider` with a method returning parsed `(date, name)` holiday records
- [x] 2.6 Add hardcoded `ENFORCEMENT_TIMEZONE = ZoneInfo("Europe/Madrid")` constant in an appropriate shared location

## 3. Infrastructure: SER zone repository updates

- [x] 3.1 `PostgresSerZoneRepository.list_all()`/`find_containing()`/`find_nearest()`: select and populate `city_code` on returned `SerZone` entities
- [x] 3.2 `PostgresSerZoneRepository.get_street_names()`/`get_zone_area()`/`list_zone_areas()`: accept/filter by `city_code`, populate it on returned `ZoneArea`
- [x] 3.3 `PostgresSerZoneRepository.bulk_replace()`: change `TRUNCATE` to `DELETE ... WHERE city_code = :city` for all three tables, scoped to the ingesting provider's city
- [x] 3.4 `IngestSerZones`/callers: confirm `city_code` is threaded through into the dicts passed to `bulk_replace()`

## 4. Infrastructure: enforcement schedule and holiday repositories

- [x] 4.1 New Postgres-backed implementation of `SerEnforcementSchedule.is_active_now()`: query `ser_timetable_weekday_hours`, `ser_timetable_exception`, and `holidays` for the given `city_code`, evaluate the precedence order (Sunday → holiday → fixed_date exception → month exception → weekday hours) against `datetime.now(ENFORCEMENT_TIMEZONE)`
- [x] 4.2 New Postgres repository method(s) for upserting `holidays` rows with `source='ical_national'` (`ON CONFLICT (city_code, date, source) DO UPDATE`), never touching `source='manual'` rows
- [x] 4.3 New Postgres repository method for checking whether a city has zero `source='ical_national'` rows (used by the scheduler's startup-conditional fetch)

## 5. Holiday provider (Google Calendar iCal)

- [x] 5.1 Add the `icalendar` dependency to `pyproject.toml`
- [x] 5.2 Implement `GoogleCalendarHolidayProvider` (or similar): `DEFAULT_HOLIDAY_ICAL_URL` constant, hostname allowlist (`calendar.google.com`), `httpx` fetch with standard-browser user agent (matching `DgtAmbientLabelProvider` convention), raises on non-2xx/network errors
- [x] 5.3 Implement iCal parsing module: parse `VEVENT` entries into `(date, name)` holiday records
- [x] 5.4 New use case `RefreshPublicHolidays` (or similar): for each enabled city, fetch via the provider and upsert via the repository method from 4.2; catches and logs provider errors without raising to the scheduler

## 6. Enforcement check wiring

- [x] 6.1 Update `DetermineSerTicketRequirement.__init__` to accept the injected `SerEnforcementSchedule` dependency
- [x] 6.2 Update `DetermineSerTicketRequirement.execute(zone)`: return `False` immediately if `zone is None`; otherwise return `enforcement_schedule.is_active_now(zone.city_code)`
- [x] 6.3 Update `app.py` DI wiring: construct the enforcement-schedule dependency and pass it into `DetermineSerTicketRequirement`
- [x] 6.4 Rewrite `provider_registry.build_providers()` to accept a DB engine, query `SELECT code FROM cities`, and build a provider per returned code (existing `code == "madrid"` dispatch logic and per-source URL env-var overrides unchanged); remove `ENABLED_CITIES` and `_KNOWN_CITIES`; log a warning and skip any `cities` row with no matching provider implementation
- [x] 6.5 Update `app.py`'s call site to pass the DB engine into `build_providers()`

## 7. Holiday refresh scheduler

- [x] 7.1 New `config.py` getters: holiday calendar URL (default-with-override, per design.md D7 — not a required/RuntimeError-if-unset getter, since a working default exists) and refresh interval hours (default matching 6 months, matching `get_ingestion_interval_hours()` convention)
- [x] 7.2 New scheduler class: APScheduler job on the configured interval; at startup, for each enabled city, check 4.3's "zero ical_national rows" condition and fire immediately only if true, otherwise wait for the next interval tick
- [x] 7.3 Wrap each city's refresh run in its own try/except (log and continue) so one city's failure doesn't stop others or crash the scheduler, matching `AmbientLabelScheduler`'s per-item isolation convention
- [x] 7.4 Wire scheduler start/shutdown into `app.py`'s lifespan alongside the existing schedulers

## 8. Tests

- [x] 8.1 Unit tests: `SerZone`/`ZoneArea` carry and expose `city_code`
- [x] 8.2 Unit tests: `SerEnforcementSchedule.is_active_now()` for every scenario in the `ser-enforcement-schedule` spec (weekday in/out of hours, Saturday reduced hours, Sunday absolute, holiday absolute, August exception, Dec 24/31 exception, fixed-date-over-month precedence, missing-holiday-data fail-open)
- [x] 8.3 Unit tests: `DetermineSerTicketRequirement` with a mocked `SerEnforcementSchedule` (zone=None short-circuits; zone present delegates to the mock; result matches the mock's answer)
- [x] 8.4 Unit tests: `PostgresSerZoneRepository.bulk_replace()` only deletes/replaces rows for the ingested `city_code`, leaving other cities' rows untouched
- [x] 8.5 Unit tests: `get_street_names()`/`get_zone_area()` filter correctly when two cities share a `zone_number`/`zone_type`
- [x] 8.6 Unit tests: `GoogleCalendarHolidayProvider` fetch/parse (mocked HTTP), hostname allowlist rejection, configurable URL override
- [x] 8.7 Unit tests: `RefreshPublicHolidays` upsert is idempotent and never modifies `source='manual'` rows
- [x] 8.8 Unit tests: scheduler's startup-conditional immediate-fetch logic (empty table fires immediately; non-empty table waits for interval)
- [x] 8.9 Integration test: migrations apply cleanly end-to-end and seeded data matches the `ser-enforcement-schedule`/`city-registry` spec scenarios (cities row, 7 weekday rows, 3 exception rows)
- [x] 8.10 Unit tests: `build_providers()` reads city codes from `cities` (mocked/test DB), skips unimplemented codes with a warning, and ignores `ENABLED_CITIES` entirely

## 9. Verification

- [x] 9.1 Run full backend test suite and confirm no regressions
- [x] 9.2 Run ruff/mypy lint and fix any findings
- [x] 9.3 Manual verification against a running stack — DONE against the user's live docker-compose stack: migrations applied cleanly on container startup; `cities` seeded with `madrid`/`Madrid`; all 6 `city_code` FK constraints confirmed live via `information_schema` query and empirically confirmed to reject an invalid `city_code` insert; `ser_timetable_weekday_hours` (7 rows) and `ser_timetable_exception` (3 rows) match spec; `provider_registry.build_providers()` built exactly 1 provider from the `cities` table with zero `ENABLED_CITIES` involvement (confirmed via container logs); `HolidayRefreshScheduler` fired its startup-conditional immediate fetch (table was empty) and upserted exactly 103 holiday rows — cross-checked against the raw feed directly (101 exact `"Día festivo"` + 2 Madrid-inclusive regional entries = 103), proving the DESCRIPTION-based filter is correct on the real feed, not just in unit tests; `PostgresSerEnforcementSchedule.is_active_now("madrid")` called directly against live data returned `False` at Saturday 22:50 Europe/Madrid (correctly outside the 09:00-15:00 Saturday window)
- [x] 9.4 Grep the codebase (source, tests, docs, `.env`/`.env.example`, README/deployment docs) for `ENABLED_CITIES` and `_KNOWN_CITIES`/`KNOWN_CITIES` and confirm zero remaining references — every occurrence must be deleted, not merely unused, including the docstring in `provider_registry.py` describing the old env-var behavior

## 10. Holiday relevance filtering (DESCRIPTION-based, per-city)

- [x] 10.1 Change `PublicHolidayProvider` port + `GoogleCalendarHolidayProvider` to return raw fetched `.ics` text (one shared HTTP fetch per run) instead of pre-parsed holiday records
- [x] 10.2 Update `parse_ical_holidays(ics_text, city_code)` to filter events per the `public-holiday-calendar` spec's new "Filter calendar events to genuine, city-applicable public holidays only" requirement: keep `DESCRIPTION == "Día festivo"` (every city); keep `DESCRIPTION` starting with `"Celebración en "` only if the target city's capitalized `city_code` is an exact entry in the following comma-separated region list; exclude everything else
- [x] 10.3 Update `RefreshPublicHolidays.execute()` to fetch the raw calendar once, then call `parse_ical_holidays(raw_text, city_code)` per enabled city before upserting that city's filtered holidays
- [x] 10.4 Update tests: `test_ical_holiday_parser.py` (national/generic-celebration/regional-included/regional-excluded/exact-match-not-substring cases), `test_google_calendar_provider.py` (raw-text return), `test_refresh_public_holidays.py` (two cities can get different holiday sets from one fetch)
- [x] 10.5 Run full test suite + ruff/mypy and confirm no regressions
