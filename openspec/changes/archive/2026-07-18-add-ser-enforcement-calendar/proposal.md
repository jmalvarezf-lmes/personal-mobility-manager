## Why

`DetermineSerTicketRequirement` currently treats every SER zone as enforced 24/7 (`zone is not None` → ticket required), so owners get notified even on Sundays, public holidays, August afternoons, and other reduced-hours periods when Madrid's SER regulation does not actually apply. The use case's own docstring already reserves an injected-dependency seam for exactly this. There is no `cities` concept anywhere in the schema yet (SER tables have no city column at all), no timetable/holiday data, and no external holiday calendar integration — all three need to be introduced together for the enforcement check to be correct.

## What Changes

- Add a `cities` table (`code` PK, `name`) as the shared reference dimension for all city-scoped data — reusing the `city_code` values (e.g. `"madrid"`) already used informally by `CityParkingDataProvider`/`provider_registry`.
- Add `ser_timetable_weekday_hours` (one row per city per weekday, start/end time, active flag) and `ser_timetable_exception` (per-city recurring overrides keyed by month or fixed month-day, e.g. August, Dec 24/31) tables, seeded via Alembic migration with Madrid's published SER hours (no external datasource for this data — it is fixed and hand-authored).
- Add a `holidays` table (per city, date, name, `source` of `ical_national` or `manual`) and a new `PublicHolidayProvider` port + Google Calendar iCal-based implementation that fetches Spain's national holiday calendar and upserts rows per enabled city, never touching `manual`-sourced rows.
- Add a scheduled refresh job for the holiday provider: 6-month interval, plus an immediate fetch on startup only if a city currently has zero `ical_national` rows (skip the immediate fetch if data already exists).
- Retrofit `city_code` onto the existing `ser_zones`, `ser_zone_streets`, and `ser_zone_areas` tables, widening `ser_zones`' unique constraint to `(city_code, zone_number, zone_type)` and `ser_zone_areas`' primary key to `(city_code, zone_number)` — required because `zone_number` alone is not guaranteed unique across cities. **BREAKING** (schema): existing rows are backfilled to `"madrid"` in the same migration.
- Scope `PostgresSerZoneRepository.bulk_replace()` to `DELETE ... WHERE city_code = :city` instead of a bare `TRUNCATE`, so ingesting one city can no longer wipe another city's rows.
- Thread `city_code` through the `SerZone` domain entity and `SerZoneRepository` port (`get_street_names`, `get_zone_area` gain a `city_code` parameter) so the enforcement check knows which city's calendar applies to a matched zone.
- Extend `DetermineSerTicketRequirement` with an injected timetable/holiday-check dependency; the check order is Sunday → holiday → fixed-date exception → month exception → weekday hours, evaluated against a hardcoded `Europe/Madrid` constant (no per-user/per-city timezone setting yet — noted as future work).
- Replace the `ENABLED_CITIES` env var and hardcoded `_KNOWN_CITIES` set in `provider_registry.py` with the `cities` table as the sole source of truth for which city codes are active. **BREAKING**: `ENABLED_CITIES` is removed and has no effect; the registry now queries `cities` at startup, requiring DB access at provider-registry construction time.
- Use the `icalendar` PyPI package (actively maintained, widely used) for parsing the Google Calendar iCal feed.

## Capabilities

### New Capabilities
- `city-registry`: the `cities` reference table and the domain concept of a supported city code, used as the shared FK target for all other city-scoped tables introduced here.
- `ser-enforcement-schedule`: per-city weekday operating hours and calendar exceptions (August, Dec 24/31) modeling when SER enforcement is actually in effect, independent of holiday status.
- `public-holiday-calendar`: the per-city `holidays` table, the Google Calendar iCal-based national holiday provider, and its 6-month/startup-conditional refresh scheduler.

### Modified Capabilities
- `ser-ticket-requirement`: `DetermineSerTicketRequirement` changes from a pure zone-presence check to also evaluating enforcement hours and holiday status via an injected port.
- `ser-zone-ingestion`: `ser_zones` and `ser_zone_streets` gain a `city_code` column with widened keys; `bulk_replace()` becomes city-scoped instead of a full-table truncate.
- `ser-zone-query`: the `SerZone` domain entity and `SerZoneRepository` port gain `city_code` (as a field and as a lookup key parameter respectively).
- `ser-zone-frontier`: the `ser_zone_areas` table gains a `city_code` column, widening its primary key to `(city_code, zone_number)`.
- `city-parking-data-provider`: the provider registry is populated from the `cities` table instead of the `ENABLED_CITIES` env var and hardcoded `_KNOWN_CITIES` set.

## Impact

- **Database**: 4 new tables (`cities`, `ser_timetable_weekday_hours`, `ser_timetable_exception`, `holidays`); schema + backfill migrations on `ser_zones`, `ser_zone_streets`, `ser_zone_areas`.
- **Domain/application**: `SerZone` entity, `SerZoneRepository` port, `DetermineSerTicketRequirement` use case, new `PublicHolidayProvider` port.
- **Infrastructure**: `PostgresSerZoneRepository` (bulk_replace scoping + new city-aware queries), `provider_registry.py` (rewritten to query `cities` instead of env var), new Google Calendar iCal fetch/parse module, new Postgres repositories for timetable/exception/holiday tables, new scheduler (alongside `ParkingIngestionScheduler`/`AmbientLabelScheduler`).
- **Dependencies**: `icalendar` (new).
- **Config**: new env vars for the holiday calendar URL and refresh interval, following existing `config.py` getter conventions; `ENABLED_CITIES` is removed.
- **No API/frontend contract changes** — this only affects whether a notification fires, not any response shape.
