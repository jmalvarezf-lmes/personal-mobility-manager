## Context

`DetermineSerTicketRequirement.execute(zone)` is currently `return zone is not None` — a pure presence check. Its docstring reserves itself as "the designated seam" for enforcement-hours, home-proximity, and resident-permit logic, each meant to arrive as an injected constructor dependency without changing `execute()`'s signature or any caller. This change fills in the enforcement-hours/holiday factor.

Madrid's published SER schedule:
- Mon–Fri: 09:00–21:00 (uninterrupted)
- Saturday: 09:00–15:00
- August: Mon–Sat (non-holiday) 09:00–15:00
- Dec 24 and Dec 31: 09:00–15:00
- Sundays and public holidays: no service

There is currently no `cities` concept in the schema at all — `city_code` (e.g. `"madrid"`) exists only as a runtime string checked against a hardcoded `_KNOWN_CITIES` set in `provider_registry.py`, gated by an `ENABLED_CITIES` env var. `ser_zones`/`ser_zone_streets`/`ser_zone_areas` have no city column. There is also no timezone handling anywhere in the app (no `zoneinfo` usage, no `Europe/Madrid` constant) — every existing scheduler uses naive server-local `datetime.now()`.

Three prior explore-mode decisions shape this design:
1. The timetable must be modeled generically enough that any future city fits the same schema (not Madrid-specific columns).
2. Regional/local holidays (not covered by the national iCal feed) will be added by hand into the same `holidays` table the automated provider writes to — the provider must never clobber those rows.
3. `provider_registry.py`'s `ENABLED_CITIES` env var and hardcoded `_KNOWN_CITIES` set are replaced outright by the new `cities` table — once a real reference table exists, having a second, independent env-var-driven mechanism for "which cities are active" would be a drift risk, not a complement.

## Goals / Non-Goals

**Goals:**
- Model SER enforcement hours and calendar exceptions per city, seeded by hand in an Alembic migration (no external datasource for the timetable itself).
- Model public holidays per city, populated automatically from Spain's national Google Calendar iCal feed, with room for hand-inserted regional/local holidays that the automated refresh never touches.
- Wire enforcement-hours + holiday evaluation into `DetermineSerTicketRequirement` via the pre-reserved injected-dependency seam.
- Retrofit `city_code` onto the existing SER zone tables so the enforcement check knows which city's calendar applies to a matched zone, correcting the latent single-city assumption baked into their current keys.

**Non-Goals:**
- No per-user or per-city configurable timezone — `Europe/Madrid` is a hardcoded constant this change. A future change may promote it to a setting.
- No automated regional/local holiday sourcing — those rows are entered by hand.
- No UI/API surface for managing timetables or holidays (DB-only for now; future admin tooling is out of scope).
- No multi-timezone SER cities — the design assumes one enforcement timezone across all cities for now, consistent with the hardcoded-constant decision.

## Decisions

### D1: `cities` as a first-class reference table
Add `cities(code TEXT PRIMARY KEY, name TEXT NOT NULL)`, reusing the existing `city_code` string values (`"madrid"`) as the PK — no new surrogate integer ID, so it joins cleanly against the string already used by `CityParkingDataProvider.city_code` and `provider_registry`. Seeded with one row (`madrid`) in the same migration that creates it.

Alternative considered: keep `city_code` as a bare stringly-typed column on each table with no FK target (matching today's informal convention). Rejected because every table added in this change needs a real FK to avoid drift between "cities the app knows about" and "cities with timetable/holiday data," and because a reference table costs nothing extra now while the schema is still greenfield for this concept.

### D2: Timetable modeled as two tables (weekday hours + exceptions), not one flexible rule table
```
ser_timetable_weekday_hours          ser_timetable_exception
- city_code (FK, PK part)            - id (PK)
- weekday (0=Mon..6=Sun, PK part)    - city_code (FK)
- start_time (TIME)                  - recurrence ('month' | 'fixed_date')
- end_time (TIME)                    - month (SMALLINT, nullable)          -- for 'month'
- active (BOOLEAN)                   - month_day (TEXT 'MM-DD', nullable)  -- for 'fixed_date'
                                      - start_time (TIME)
                                      - end_time (TIME)
                                      - description (TEXT)
```
One row per `(city_code, weekday)` in the base table (Sunday's row has `active=false`); exceptions layer on top for August (`recurrence='month', month=8`) and Dec 24/31 (two `recurrence='fixed_date'` rows, `month_day='12-24'`/`'12-31'`). Evaluation order (see D4) checks fixed-date exceptions first, then month exceptions, then falls back to the weekday row.

Alternative considered: a single generic `rule + priority` table (closer to how general-purpose "opening hours" engines model recurrence, e.g. one row type with a precedence column resolving overlaps). Rejected: for a hand-authored, rarely-changing seed with exactly one exception-shape (month-wide or fixed-date override), two literal tables are more legible in the migration diff and in ad-hoc debugging ("why wasn't I notified on Aug 15" → look in one small exceptions table) than a generic priority-resolution engine that has no other consumer today.

### D3: Holidays table with a `source` column to protect hand-entered rows
```
holidays
- id (PK)
- city_code (FK)
- date (DATE)
- name (TEXT)
- source ('ical_national' | 'manual')
- UNIQUE (city_code, date, source)   -- allows a manual regional holiday and an
                                       -- ical_national row to coexist on the same
                                       -- date without collision, but prevents
                                       -- duplicate refresh inserts
```
The refresh job only ever inserts/upserts rows with `source='ical_national'` (`ON CONFLICT (city_code, date, source) DO UPDATE SET name = EXCLUDED.name`) and never issues a blanket delete — so `source='manual'` rows (regional/local holidays entered by hand) are never touched by the automated job. National holidays are duplicated per enabled city (one row per city per date) since the table is "holidays by city," even though the underlying feed is nationwide — this matches how the enforcement check queries (`WHERE city_code = :city AND date = :today`).

Alternative considered: `city_code` nullable to mean "applies to all cities" for national holidays, avoiding duplication. Rejected: the enforcement check would need an `OR city_code IS NULL` branch on every lookup, and the duplication cost is trivial (one row per city per holiday per year).

### D4: Enforcement-hours check order and injection point
`DetermineSerTicketRequirement` gains a constructor-injected port (e.g. `SerEnforcementSchedule`) — `execute(zone)`'s signature is unchanged, per the existing seam contract:
```python
class DetermineSerTicketRequirement:
    def __init__(self, enforcement_schedule: SerEnforcementSchedulePort):
        self._enforcement_schedule = enforcement_schedule

    def execute(self, zone: SerZone | None) -> bool:
        if zone is None:
            return False
        return self._enforcement_schedule.is_active_now(city_code=zone.city_code)
```
`is_active_now` evaluates, in order, against `datetime.now(ZoneInfo("Europe/Madrid"))`:
1. Is today Sunday? → not active (absolute — holidays and exceptions cannot override this)
2. Is today a holiday for this city (`holidays` table)? → not active (also absolute)
3. Does a `fixed_date` exception match today's month-day? → use its hours
4. Does a `month` exception match today's month? → use its hours
5. Otherwise → use today's `ser_timetable_weekday_hours` row

Sunday and holiday checks are evaluated *before* exceptions and always win — confirmed against the ordinance text ("Domingos y festivos: Sin servicio" reads as unconditional), so a Dec 24 that happens to fall on a Sunday is still "no service," not "09:00–15:00."

Alternative considered: giving fixed-date exceptions precedence over the holiday check (so a Dec 24 that's also a declared holiday would still get reduced hours). Rejected per explicit decision: Sunday/holiday always wins.

### D5: `city_code` retrofit onto `ser_zones` / `ser_zone_streets` / `ser_zone_areas`
Add `city_code TEXT NOT NULL REFERENCES cities(code)` to all three tables, backfilled to `'madrid'` for existing rows in the same migration. Widen keys, since `zone_number` alone is not guaranteed unique across cities:
- `ser_zones`: `UniqueConstraint(zone_number, zone_type)` → `UniqueConstraint(city_code, zone_number, zone_type)`
- `ser_zone_areas`: PK `zone_number` → composite PK `(city_code, zone_number)`
- `ser_zone_streets`: index `(zone_number, zone_type)` → `(city_code, zone_number, zone_type)`

`SerZone` domain entity gains a `city_code: str` field (populated by `PostgresSerZoneRepository.list_all()` from the new column) so `DetermineSerTicketRequirement` can resolve which city's schedule applies without a second lookup. `SerZoneRepository.get_street_names` and `get_zone_area` gain a `city_code` parameter to match the widened keys.

### D6: `bulk_replace()` becomes city-scoped
`PostgresSerZoneRepository.bulk_replace()` currently does a bare `TRUNCATE ser_zones` / `ser_zone_streets` / `ser_zone_areas` — harmless today because exactly one city is ever ingested, but it would silently wipe every other city's rows the moment a second city is enabled, since `IngestSerZones` calls this same repo once per registered provider. Change to `DELETE FROM ser_zones WHERE city_code = :city` (and same for the other two tables) inside the existing transaction, parameterized by the city being re-ingested. This closes the gap while the tables are already being touched for D5, rather than leaving it for whoever enables city #2.

### D7: New `PublicHolidayProvider` port + Google Calendar iCal implementation
Mirrors the existing provider pattern (`CityParkingDataProvider` / `MadridSerStreetsProvider`, `AmbientLabelLookupPort` / `DgtAmbientLabelProvider`):
- Domain port: `PublicHolidayProvider` ABC with `fetch_holidays() -> list[HolidayRecord]` (date + name).
- Infra implementation: fetches `https://calendar.google.com/calendar/ical/es.spain%23holiday%40group.v.calendar.google.com/public/basic.ics` (default, overridable via env var, following the `DEFAULT_*_URL` + override convention), enforces a hostname allowlist (`calendar.google.com`) matching the `DgtAmbientLabelProvider`/`MadridCallejeroCsvFetcher` convention, parses via the `icalendar` PyPI package (chosen over alternatives like `ics` for being more actively maintained and more widely used; none exists in the project today — all existing parsers are CSV/shapefile-based).
- A new use case (e.g. `RefreshPublicHolidays`) applies fetched records to all cities present in the `cities` table via the upsert described in D3.

### D8: Holiday refresh scheduler cadence
A new scheduler job: 6-month fixed interval as steady cadence. At startup, the job fires immediately **only if** the `holidays` table has zero `source='ical_national'` rows for a given enabled city; otherwise it skips the immediate run and waits for the next interval tick. This deliberately diverges from the existing schedulers (`ParkingIngestionScheduler`, `AmbientLabelScheduler`), which always fire unconditionally via `next_run_time=datetime.now()` — holidays change rarely enough that an unconditional refresh on every deploy/restart is unnecessary churn, but a cold/empty table (first deploy, or a newly onboarded city) must not wait up to 6 months for its first data.

### D9: Hardcoded timezone constant
Introduce a single module-level constant, e.g. `ENFORCEMENT_TIMEZONE = ZoneInfo("Europe/Madrid")`, used wherever "now" is evaluated for the enforcement/holiday check. Not stored in the `cities` table and not exposed as a setting in this change — noted explicitly as a placeholder for a future per-user or per-city preference, per the decision to defer that.

### D11: Filter calendar events by `DESCRIPTION`, applied per city, not just parsed wholesale
Verified directly against the live feed (fetched and inspected the actual `.ics` payload) that Google's Spain holiday calendar mixes real public holidays with non-holiday "celebrations" (Carnival, Father's Day, Easter Sunday, New Year's Eve, DST changes) as ordinary `VEVENT`s indistinguishable by `SUMMARY` alone. The distinguishing field is `DESCRIPTION`:
- Real national holidays: `DESCRIPTION:Día festivo` (exact).
- Non-holiday celebrations: `DESCRIPTION:Celebración\nPara ocultar las celebraciones, ve a Configuración en Google Calendar > Festivos en España` (generic, no region list).
- A third, initially-missed category: some years label an actual holiday (e.g. Labour Day, Christmas) as `"(festivo regional)"` in `SUMMARY` with `DESCRIPTION:Celebración en <comma-separated region list>\nPara ocultar...` — verified one such 2022-05-01 entry whose region list includes `Madrid`, meaning it IS a real Madrid holiday that year despite not using the `"Día festivo"` label.

Filtering rule (applied per target city, not once globally): keep an event if `DESCRIPTION == "Día festivo"` (applies to every city), OR if `DESCRIPTION` starts with `"Celebración en "` and the target city's capitalized `city_code` appears as an exact entry in the following comma-separated list; exclude everything else (generic celebrations, or regional lists that don't name the target city).

This makes the two-layer fetch/parse split from D7 more valuable than originally scoped: the raw `.ics` fetch stays a single shared HTTP call (`PublicHolidayProvider` now returns raw text, not pre-parsed records), but parsing+filtering now happens once per enabled city against that same raw text, since two cities can legitimately get different holiday sets from one fetch (a regional entry naming Madrid but not Barcelona). `RefreshPublicHolidays.execute()` fetches once, then loops `parse_ical_holidays(raw_text, city_code)` per city before upserting.

Alternative considered: match city by looking up `cities.name` (the DB's own display-name column, already `"Madrid"` for `code="madrid"`) instead of algorithmically capitalizing `city_code` in the parser. Rejected for now to keep `parse_ical_holidays` a pure, DB-independent function — `city_code.capitalize()` produces the identical string to `cities.name` for every city that exists today, and this is a two-string coincidence worth re-examining only if a future multi-word city code (e.g. `las_palmas`) is onboarded, since `.capitalize()` would not produce `"Las Palmas"`.

Alternative considered: match the target city name via substring (`city_name in description`) instead of splitting the region list and comparing exact trimmed entries. Rejected: a substring check risks false positives if one region's name is a prefix/substring of another's (not currently observed in Spain's region names, but exact-match-on-list-membership is strictly safer and no more complex).

### D10: `provider_registry.py` reads from `cities` instead of `ENABLED_CITIES`/`_KNOWN_CITIES`
`build_providers()` currently reads the `ENABLED_CITIES` env var (comma-separated, default `"madrid"`), splits it, and checks each code against a hardcoded `_KNOWN_CITIES = {"madrid"}` set — logging and skipping anything not in that set. This is replaced: `build_providers()` gains a required `engine: Engine` (or equivalent DB-access) parameter, queries `SELECT code FROM cities`, and for each returned code either constructs the matching provider (the `code == "madrid"` dispatch logic itself is unchanged — a DB row cannot contain executable construction logic, so a code-level mapping from `city_code` to provider class still exists) or logs a warning and skips it if no implementation is registered for that code. `ENABLED_CITIES` is removed entirely; per-source URL overrides (`SER_ZONE_SHP_URL`, `MADRID_CALLEJERO_URL`, `MADRID_BARRIOS_SHP_URL`) are unaffected since they configure a provider's own sources, not which cities are active.

This inverts the failure direction from today: previously an *env var* entry with no implementation was the anomaly ("ENABLED_CITIES contains unknown city code"); now a *cities table row* with no implementation is the anomaly ("cities table contains code with no registered provider"). Enabling a new city becomes "insert a row into `cities` (via migration, matching this change's own pattern) and register its provider class in code" rather than "set an env var" — consistent with the broader shift this change makes toward `cities` being the source of truth.

Alternative considered: keep `ENABLED_CITIES` as an additional filter on top of `cities` (i.e., a city must be both in the table and in the env var to be enabled). Rejected per explicit decision — a single source of truth is the point; a second gate reintroduces the exact drift risk (table says one thing, env var says another) that motivated the change.

## Risks / Trade-offs

- **[Risk]** Google's public iCal feed changes format, becomes unreachable, or rate-limits → the refresh job fails silently for 6 months. **Mitigation**: log failures loudly (matching `MadridSerStreetsProvider`'s "log which source failed, leave existing data intact" convention); the check gracefully degrades to "not a holiday" if a date is simply absent, which is a safe direction to fail (worst case: an occasional false notification on an actual holiday, not a wrongly suppressed one — but see below).
- **[Risk]** Fail-open on missing/stale holiday data (confirmed decision, D-level: missing row ≠ holiday) means under-listed holidays produce an occasional false notification rather than suppressing real ones — accepted as the safer failure direction for this product's purpose.
- **[Risk]** Widening `ser_zones`/`ser_zone_areas` keys and backfilling `city_code='madrid'` is a breaking schema change touching production data. **Mitigation**: single migration does add-column-with-default + backfill + constraint-widen in one transaction, consistent with existing migration conventions (`p3q4r5s6t7u8_create_notification_types.py` style for schema+seed; no separate backfill migration needed since there's only ever been one city's worth of rows).
- **[Trade-off]** Sunday/holiday absolute precedence over exceptions (D4) means a hand-entered future ordinance change (e.g. a city where Sunday IS enforced) would require a schema change, not just a data change. Accepted per explicit decision — matches the literal Madrid ordinance text, and no other city is in scope today.
- **[Risk]** New `icalendar` dependency is the project's first non-CSV/shapefile parser dependency — supply-chain surface increases marginally. **Mitigation**: `icalendar` is a well-maintained, widely-used PyPI package; no alternative avoids this, since hand-rolling `.ics` parsing is worse than depending on a standard package for the format.
- **[Risk]** `build_providers()` now requires DB access at construction time (D10), whereas today it's a pure env-var read — if the DB is unreachable at startup, provider construction fails instead of degrading to defaults. **Mitigation**: this is consistent with the rest of `app.py`'s startup, which already requires a working DB connection for every other repository; no new failure mode is introduced, just an earlier point where an existing dependency (DB availability) is required.

## Migration Plan

1. Migration A: create `cities` (schema + seed `madrid` row).
2. Migration B: create `ser_timetable_weekday_hours` + `ser_timetable_exception` (schema + seed Madrid's fixed hours/exceptions), FK to `cities`.
3. Migration C: create `holidays` (schema only, no seed rows — first data arrives via D8's startup-conditional fetch).
4. Migration D: add `city_code` to `ser_zones`/`ser_zone_streets`/`ser_zone_areas`, backfill `'madrid'`, widen unique constraint / PK / index as per D5. Update `infrastructure/orm/tables.py` to match (shared source of truth for alembic autogenerate).
5. Code: `PostgresSerZoneRepository.bulk_replace()` scoping (D6); `SerZone`/`SerZoneRepository` city_code threading (D5); `PublicHolidayProvider` port + Google Calendar implementation (using `icalendar`) + refresh use case + scheduler (D7/D8); `DetermineSerTicketRequirement` injected dependency (D4); `provider_registry.py` rewrite to query `cities` (D10); new `config.py` getters for the iCal URL and refresh interval; remove `ENABLED_CITIES` references.
6. Rollback: each schema migration has a symmetric `downgrade()` (drop table / narrow constraint back). Migration D's downgrade drops the `city_code` columns and reverts keys — safe only as long as no second city has been onboarded in between (documented in the migration's downgrade docstring, consistent with the existing "intentionally non-reversible" precedent in `r5s6t7u8v9w0_backfill_user_notification_preferences.py` for irreversible data migrations).

## Open Questions

None outstanding — fail-open behavior, the `icalendar` package choice, and the `provider_registry.py`/`cities` consolidation (D10) were all confirmed during design review.
