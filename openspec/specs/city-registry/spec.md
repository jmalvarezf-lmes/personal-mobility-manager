### Requirement: cities database table
The system SHALL maintain a `cities` table in PostgreSQL with columns: `code` (text, primary key, e.g. `"madrid"`), `name` (text, not-null). This table is the shared reference dimension for every other city-scoped table, reusing the `city_code` values already used informally by `CityParkingDataProvider.city_code` and `provider_registry`.

#### Scenario: Table created and seeded by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `cities` table is created if it does not already exist, and contains a row with `code='madrid'`

#### Scenario: Duplicate code rejected
- **WHEN** an insert would create a second row with `code='madrid'`
- **THEN** the primary key constraint rejects it

---

### Requirement: cities as FK target for city-scoped tables
Every table introduced or modified by this change to carry a `city_code` column (`ser_timetable_weekday_hours`, `ser_timetable_exception`, `holidays`, `ser_zones`, `ser_zone_streets`, `ser_zone_areas`) SHALL declare a foreign key against `cities.code`.

#### Scenario: Insert with unknown city_code rejected
- **WHEN** an insert into any city-scoped table references a `city_code` with no matching row in `cities`
- **THEN** the foreign key constraint rejects it

---

### Requirement: GET /cities lists all registered cities
The system SHALL expose `GET /cities` returning a JSON array of all rows in the `cities` table, each with `code` and `name`. This endpoint requires no authentication and SHALL always reflect the live table contents.

#### Scenario: Successful query returns all cities
- **WHEN** a GET request is made to `/cities`
- **THEN** the response status is 200 with a JSON array where each element has `code` and `name`, matching every row currently in the `cities` table

#### Scenario: A newly seeded city appears without a code change
- **WHEN** a new row is added to the `cities` table
- **THEN** a subsequent `GET /cities` request includes it, with no application code change required
