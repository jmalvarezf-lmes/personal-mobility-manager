## ADDED Requirements

### Requirement: vehicle_ser_parking_exemptions database table
The system SHALL maintain a `vehicle_ser_parking_exemptions` table in PostgreSQL with columns: `vehicle_id` (uuid, primary key, references `vehicles.id` with `ON DELETE CASCADE`), `city_code` (text, not-null), `zone_number` (varchar(10), not-null), `updated_at` (timestamptz, not-null). The table SHALL declare a composite foreign key `(city_code, zone_number)` referencing `ser_zone_areas(city_code, zone_number)`. At most one row SHALL exist per vehicle.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `vehicle_ser_parking_exemptions` table with its primary key and composite foreign key is created if it does not already exist

#### Scenario: Vehicle deletion cascades to its exemption
- **WHEN** a `Vehicle` row with an existing exemption row is deleted
- **THEN** the corresponding `vehicle_ser_parking_exemptions` row is also deleted, without a separate delete call

#### Scenario: Referencing a zone_number absent from ser_zone_areas is rejected
- **WHEN** an insert or update targets a `(city_code, zone_number)` pair with no matching `ser_zone_areas` row
- **THEN** the composite foreign key constraint rejects it

### Requirement: VehicleSerParkingExemptionRepository port and Postgres implementation
The system SHALL define a `VehicleSerParkingExemptionRepository` abstract port with `find_by_vehicle_id(vehicle_id) -> VehicleSerParkingExemption | None`, `upsert(vehicle_id, city_code, zone_number) -> VehicleSerParkingExemption`, and `delete(vehicle_id) -> None`, and a Postgres-backed implementation. `upsert` SHALL replace any existing row for the vehicle (insert-or-update semantics on the `vehicle_id` primary key). `delete` SHALL be idempotent — deleting a vehicle with no existing exemption row SHALL NOT raise.

#### Scenario: Upsert replaces an existing exemption
- **WHEN** `upsert` is called for a vehicle that already has an exemption for a different `(city_code, zone_number)`
- **THEN** the vehicle's single row is updated to the new `(city_code, zone_number)`, not duplicated

#### Scenario: find_by_vehicle_id returns None when unset
- **WHEN** `find_by_vehicle_id` is called for a vehicle with no exemption row
- **THEN** it returns `None`

#### Scenario: Delete is idempotent
- **WHEN** `delete` is called for a vehicle with no existing exemption row
- **THEN** it completes without raising

### Requirement: GET /vehicles/{id}/ser-parking-exemptions returns the vehicle's exemption
The system SHALL expose `GET /vehicles/{id}/ser-parking-exemptions` requiring a valid JWT session cookie. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle not owned by the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404. When the vehicle exists and is owned by the caller, the response SHALL be HTTP 200 with `{ "city_code": ..., "zone_number": ... }` if an exemption exists, or `{ "city_code": null, "zone_number": null }` if none is set.

#### Scenario: Owner retrieves an existing exemption
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/ser-parking-exemptions` for a vehicle with a stored exemption
- **THEN** the response is HTTP 200 with the stored `city_code` and `zone_number`

#### Scenario: Owner retrieves when no exemption is set
- **WHEN** an authenticated owner sends `GET /vehicles/{id}/ser-parking-exemptions` for a vehicle with no exemption row
- **THEN** the response is HTTP 200 with `city_code: null` and `zone_number: null`

#### Scenario: Non-owner receives 403
- **WHEN** an authenticated user sends `GET /vehicles/{id}/ser-parking-exemptions` for a vehicle owned by a different user
- **THEN** the response is HTTP 403

#### Scenario: Non-existent vehicle returns 404
- **WHEN** an authenticated user sends `GET /vehicles/{id}/ser-parking-exemptions` with an unknown vehicle UUID
- **THEN** the response is HTTP 404

### Requirement: POST /vehicles/{id}/ser-parking-exemptions sets or replaces the vehicle's exemption
The system SHALL expose `POST /vehicles/{id}/ser-parking-exemptions` requiring a valid JWT session cookie, with a request body `{ "city_code": string, "zone_number": string }`. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle not owned by the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404. A `(city_code, zone_number)` pair with no matching `ser_zone_areas` row SHALL return HTTP 422. On success the system SHALL upsert the exemption and return HTTP 200 with the stored values.

#### Scenario: Owner sets a new exemption
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` with a valid `city_code` and `zone_number` for a vehicle with no existing exemption
- **THEN** a new row is created and the response is HTTP 200 with the stored `city_code` and `zone_number`

#### Scenario: Owner replaces an existing exemption
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` for a vehicle that already has a different exemption stored
- **THEN** the existing row is replaced with the new `(city_code, zone_number)`, not duplicated

#### Scenario: Unknown zone_number is rejected
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` with a `(city_code, zone_number)` pair absent from `ser_zone_areas`
- **THEN** the response is HTTP 422

#### Scenario: Non-owner receives 403
- **WHEN** an authenticated user sends `POST /vehicles/{id}/ser-parking-exemptions` for a vehicle owned by a different user
- **THEN** the response is HTTP 403

#### Scenario: Non-existent vehicle returns 404
- **WHEN** an authenticated user sends `POST /vehicles/{id}/ser-parking-exemptions` with an unknown vehicle UUID
- **THEN** the response is HTTP 404

### Requirement: DELETE /vehicles/{id}/ser-parking-exemptions clears the vehicle's exemption
The system SHALL expose `DELETE /vehicles/{id}/ser-parking-exemptions` requiring a valid JWT session cookie. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle not owned by the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404. On success the system SHALL delete any existing exemption row and return HTTP 204, whether or not a row previously existed.

#### Scenario: Owner clears an existing exemption
- **WHEN** an authenticated owner sends `DELETE /vehicles/{id}/ser-parking-exemptions` for a vehicle with a stored exemption
- **THEN** the row is deleted and the response is HTTP 204

#### Scenario: Clearing when none is set is a no-op success
- **WHEN** an authenticated owner sends `DELETE /vehicles/{id}/ser-parking-exemptions` for a vehicle with no exemption row
- **THEN** the response is HTTP 204 without raising an error

#### Scenario: Non-owner receives 403
- **WHEN** an authenticated user sends `DELETE /vehicles/{id}/ser-parking-exemptions` for a vehicle owned by a different user
- **THEN** the response is HTTP 403

### Requirement: Vehicle edit flow offers a city-then-zone exemption picker
The frontend vehicle edit flow SHALL offer a two-step picker for the vehicle's SER parking exemption: a city selector populated from `GET /cities`, followed by a SER zone selector (populated from `GET /parking/ser-zones?city=<selected>`'s `frontiers` array) displaying each option by its `neighbourhood` name. Selecting a zone and saving SHALL call `POST /vehicles/{id}/ser-parking-exemptions`. A visible "clear" action SHALL call `DELETE /vehicles/{id}/ser-parking-exemptions`. The zone selector SHALL be disabled or empty until a city is chosen.

#### Scenario: City list loads before zone selection is available
- **WHEN** the vehicle edit flow's exemption picker is opened
- **THEN** the city selector is populated from `GET /cities` and the zone selector has no options until a city is chosen

#### Scenario: Choosing a city loads its SER zones labeled by neighbourhood
- **WHEN** the user selects a city in the picker
- **THEN** the zone selector is populated from that city's `GET /parking/ser-zones` `frontiers` array, with each option displaying its `neighbourhood` name

#### Scenario: Saving a selection persists the exemption
- **WHEN** the user selects a city and zone and confirms
- **THEN** `POST /vehicles/{id}/ser-parking-exemptions` is called with the selected `city_code` and `zone_number`

#### Scenario: Clearing removes the stored exemption
- **WHEN** the user triggers the clear action on a vehicle with a stored exemption
- **THEN** `DELETE /vehicles/{id}/ser-parking-exemptions` is called
