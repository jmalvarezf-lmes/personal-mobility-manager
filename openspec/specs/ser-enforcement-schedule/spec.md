### Requirement: ser_timetable_weekday_hours database table
The system SHALL maintain a `ser_timetable_weekday_hours` table in PostgreSQL with columns: `city_code` (text, references `cities.code`), `weekday` (smallint, 0=Monday..6=Sunday), `start_time` (time), `end_time` (time), `active` (boolean), with primary key `(city_code, weekday)`. Exactly one row SHALL exist per `(city_code, weekday)` combination. This table SHALL be seeded via Alembic migration with no external datasource, since the timetable is fixed and hand-authored.

#### Scenario: Table created and seeded by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_timetable_weekday_hours` table is created if it does not already exist, and contains seven rows for `city_code='madrid'` (one per weekday) matching Madrid's published SER hours: Mon-Fri `09:00-21:00` (`active=true`), Saturday `09:00-15:00` (`active=true`), Sunday (`active=false`)

#### Scenario: Sunday row is inactive
- **WHEN** looking up the `city_code='madrid'`, `weekday=6` (Sunday) row
- **THEN** `active` is `false`, meaning no service regardless of `start_time`/`end_time` values

---

### Requirement: ser_timetable_exception database table
The system SHALL maintain a `ser_timetable_exception` table in PostgreSQL with columns: `id` (serial PK), `city_code` (text, references `cities.code`), `recurrence` (text, `'month'` or `'fixed_date'`), `month` (smallint, nullable, populated only when `recurrence='month'`), `month_day` (text, nullable, format `'MM-DD'`, populated only when `recurrence='fixed_date'`), `start_time` (time), `end_time` (time), `description` (text). This table SHALL be seeded via Alembic migration with no external datasource.

#### Scenario: Table created and seeded by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `ser_timetable_exception` table is created if it does not already exist, and contains three rows for `city_code='madrid'`: one `recurrence='month'` row with `month=8` and hours `09:00-15:00` (August), and two `recurrence='fixed_date'` rows with `month_day='12-24'` and `month_day='12-31'`, each with hours `09:00-15:00`

#### Scenario: Month exception does not specify a month_day
- **WHEN** a row has `recurrence='month'`
- **THEN** its `month_day` column is `NULL` and its `month` column is populated

#### Scenario: Fixed-date exception does not specify a month
- **WHEN** a row has `recurrence='fixed_date'`
- **THEN** its `month` column is `NULL` and its `month_day` column is populated

---

### Requirement: SerEnforcementSchedule evaluates enforcement status for a city and instant
The system SHALL implement a port/use case (`SerEnforcementSchedule` or equivalent) exposing `is_active_now(city_code: str) -> bool`, evaluating the current instant as `datetime.now(ZoneInfo("Europe/Madrid"))` (a hardcoded timezone constant — no per-user or per-city timezone configuration exists yet) in this precedence order:
1. If today is Sunday: not active.
2. Else if today is a holiday for `city_code` (see the `public-holiday-calendar` capability): not active.
3. Else if a `ser_timetable_exception` row with `recurrence='fixed_date'` matches today's month-day for `city_code`: active if the current time falls within that row's `start_time`/`end_time`.
4. Else if a `ser_timetable_exception` row with `recurrence='month'` matches today's month for `city_code`: active if the current time falls within that row's `start_time`/`end_time`.
5. Else: active if `ser_timetable_weekday_hours` for `city_code` and today's weekday has `active=true` and the current time falls within its `start_time`/`end_time`.

Sunday and holiday checks (steps 1-2) are absolute and SHALL NOT be overridden by any exception match — a fixed-date exception landing on a Sunday or a declared holiday still results in "not active."

#### Scenario: Weekday within normal hours is active
- **WHEN** `is_active_now("madrid")` is called on a Wednesday at 14:00 Europe/Madrid time, with no matching holiday or exception
- **THEN** it returns `True` (within the 09:00-21:00 weekday window)

#### Scenario: Weekday outside normal hours is not active
- **WHEN** `is_active_now("madrid")` is called on a Wednesday at 22:00 Europe/Madrid time
- **THEN** it returns `False`

#### Scenario: Saturday uses reduced hours
- **WHEN** `is_active_now("madrid")` is called on a Saturday at 14:00 Europe/Madrid time, with no matching exception
- **THEN** it returns `True` (within the 09:00-15:00 Saturday window); at 16:00 it returns `False`

#### Scenario: Sunday is never active regardless of exceptions
- **WHEN** `is_active_now("madrid")` is called on a Sunday, even one matching a `fixed_date` exception (e.g. Dec 24 falling on a Sunday)
- **THEN** it returns `False`

#### Scenario: Holiday is never active regardless of exceptions
- **WHEN** `is_active_now("madrid")` is called on a date with a matching `holidays` row for `"madrid"`, even one matching a `fixed_date` or `month` exception
- **THEN** it returns `False`

#### Scenario: August applies reduced hours on non-holiday weekdays and Saturdays
- **WHEN** `is_active_now("madrid")` is called on a non-holiday Tuesday in August at 14:00 Europe/Madrid time
- **THEN** it returns `True` (within the August exception's 09:00-15:00 window, overriding the normal 09:00-21:00 weekday hours); at 16:00 it returns `False`

#### Scenario: Dec 24 and Dec 31 apply reduced hours regardless of weekday
- **WHEN** `is_active_now("madrid")` is called on Dec 24 or Dec 31 (a non-Sunday, non-holiday date) at 14:00 Europe/Madrid time
- **THEN** it returns `True` (within the fixed-date exception's 09:00-15:00 window), even if that weekday's normal hours would otherwise extend to 21:00

#### Scenario: Fixed-date exception takes precedence over month exception
- **WHEN** `is_active_now("madrid")` is called on Aug 31 (matching both the August month exception and no fixed-date exception) versus a hypothetical date matching both a fixed-date and a month exception
- **THEN** the fixed-date exception's hours are used whenever both a fixed-date and a month exception match the same date

#### Scenario: Missing holiday data fails open (treated as not a holiday)
- **WHEN** `is_active_now("madrid")` is called on a date with no matching row in `holidays` for `"madrid"` (e.g. the national calendar feed is unreachable, stale, or the city was only just onboarded)
- **THEN** the holiday check (step 2) is treated as not matching, and evaluation proceeds to the exception/weekday-hours steps as normal — the absence of data does not itself suppress the notification
