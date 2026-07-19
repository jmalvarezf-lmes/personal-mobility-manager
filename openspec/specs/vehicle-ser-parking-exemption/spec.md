### Requirement: vehicle_ser_parking_exemptions database table
The system SHALL maintain a `vehicle_ser_parking_exemptions` table in PostgreSQL with columns: `vehicle_id` (uuid, primary key, references `vehicles.id` with `ON DELETE CASCADE`), `city_code` (text, not-null), `zone_number` (varchar(10), not-null), `updated_at` (timestamptz, not-null). The table SHALL declare a composite foreign key `(city_code, zone_number)` referencing `ser_zone_areas(city_code, zone_number)` with `ON DELETE CASCADE`, so a zone that is genuinely removed from a city's dataset (no longer present in `ser_zone_areas`) cascades away any exemption pointing at it. At most one row SHALL exist per vehicle.

#### Scenario: Table created by migration
- **WHEN** the `db-migrate` Makefile target runs
- **THEN** the `vehicle_ser_parking_exemptions` table with its primary key and composite foreign key is created if it does not already exist

#### Scenario: Vehicle deletion cascades to its exemption
- **WHEN** a `Vehicle` row with an existing exemption row is deleted
- **THEN** the corresponding `vehicle_ser_parking_exemptions` row is also deleted, without a separate delete call

#### Scenario: Referencing a zone_number absent from ser_zone_areas is rejected
- **WHEN** an insert or update targets a `(city_code, zone_number)` pair with no matching `ser_zone_areas` row
- **THEN** the composite foreign key constraint rejects it

#### Scenario: A zone genuinely retired from a city's dataset cascades away its exemption
- **WHEN** SER zone re-ingestion for a city no longer produces a `ser_zone_areas` row for a given `zone_number` (the zone was retired) and a vehicle has an exemption referencing it
- **THEN** the `ser_zone_areas` row for that `zone_number` is deleted, and the referencing `vehicle_ser_parking_exemptions` row is cascaded away with it

#### Scenario: Re-ingestion of an unchanged zone_number does not disturb an existing exemption
- **WHEN** SER zone re-ingestion for a city produces a fresh `ser_zone_areas` row for a `zone_number` that a vehicle's exemption already references (e.g. its `neighbourhood`/geometry got refreshed but the zone_number is unchanged)
- **THEN** the existing `vehicle_ser_parking_exemptions` row for that vehicle is left completely undisturbed (same `updated_at`), because re-ingestion upserts unchanged `ser_zone_areas` rows rather than deleting and re-inserting them

### Requirement: VehicleSerParkingExemptionRepository port and Postgres implementation
The system SHALL define a `VehicleSerParkingExemptionRepository` abstract port with `find_by_vehicle_id(vehicle_id) -> VehicleSerParkingExemption | None`, `upsert(vehicle_id, city_code, zone_number) -> VehicleSerParkingExemption`, and `delete(vehicle_id) -> None`, and a Postgres-backed implementation. `upsert` SHALL replace any existing row for the vehicle (insert-or-update semantics on the `vehicle_id` primary key). `delete` SHALL be idempotent — deleting a vehicle with no existing exemption row SHALL NOT raise. `upsert` SHALL discriminate an `IntegrityError` by the violated constraint's name, translating only the composite `(city_code, zone_number)` FK violation into `InvalidSerParkingExemptionZoneError`; any other constraint violation (e.g. the `vehicle_id` FK, should the vehicle no longer exist) SHALL propagate unchanged rather than being mislabeled as an invalid zone.

#### Scenario: Upsert replaces an existing exemption
- **WHEN** `upsert` is called for a vehicle that already has an exemption for a different `(city_code, zone_number)`
- **THEN** the vehicle's single row is updated to the new `(city_code, zone_number)`, not duplicated

#### Scenario: find_by_vehicle_id returns None when unset
- **WHEN** `find_by_vehicle_id` is called for a vehicle with no exemption row
- **THEN** it returns `None`

#### Scenario: Delete is idempotent
- **WHEN** `delete` is called for a vehicle with no existing exemption row
- **THEN** it completes without raising

#### Scenario: A vehicle_id FK violation is not mislabeled as an invalid zone
- **WHEN** `upsert` is called and the underlying insert violates the `vehicle_id -> vehicles.id` foreign key (e.g. the vehicle no longer exists) rather than the composite zone FK
- **THEN** the original `IntegrityError` propagates unchanged, not `InvalidSerParkingExemptionZoneError`

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
The system SHALL expose `POST /vehicles/{id}/ser-parking-exemptions` requiring a valid JWT session cookie, with a request body `{ "city_code": string, "zone_number": string }`. `zone_number` SHALL be rejected with HTTP 422 if it exceeds the stored column's length (10 characters) — validated at the request-schema layer so an over-length value never reaches Postgres as an unhandled `DataError`. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle not owned by the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404. A `(city_code, zone_number)` pair with no matching `ser_zone_areas` row SHALL return HTTP 422. On success the system SHALL upsert the exemption and return HTTP 200 with the stored values.

#### Scenario: Owner sets a new exemption
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` with a valid `city_code` and `zone_number` for a vehicle with no existing exemption
- **THEN** a new row is created and the response is HTTP 200 with the stored `city_code` and `zone_number`

#### Scenario: Owner replaces an existing exemption
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` for a vehicle that already has a different exemption stored
- **THEN** the existing row is replaced with the new `(city_code, zone_number)`, not duplicated

#### Scenario: Unknown zone_number is rejected
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` with a `(city_code, zone_number)` pair absent from `ser_zone_areas`
- **THEN** the response is HTTP 422

#### Scenario: Over-length zone_number is rejected before reaching the use case
- **WHEN** an authenticated owner sends `POST /vehicles/{id}/ser-parking-exemptions` with a `zone_number` longer than 10 characters
- **THEN** the response is HTTP 422 and the underlying use case/repository is never invoked

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

### Requirement: Vehicle edit flow offers a city-then-zone exemption picker with a single unified save action
The frontend vehicle edit flow SHALL offer a two-step picker for the vehicle's SER parking exemption: a city selector populated from `GET /cities`, followed by a SER zone selector populated from `GET /parking/ser-zone-options?city=<selected>&sort=asc` (see `zones-bulk-query`'s lightweight zone-options endpoint — not the heavier `GET /parking/ser-zones`, which also returns full zone/frontier geometry unneeded for a text `<select>`), displaying each option by its `neighbourhood` name in ascending alphabetical order. The zone selector SHALL be disabled or empty until a city is chosen, and SHALL show a distinct loading state while the vehicle's current exemption and the chosen city's zone options are being fetched, rather than appearing blank/unselected. A "Clear" action SHALL reset the picker's selection locally (city and zone fields emptied) without an immediate API call. The dialog's single "Save" action SHALL persist both the vehicle's other edited fields and the exemption picker's state together, in one submission: if a city and zone are selected, it SHALL upsert the exemption (`POST /vehicles/{id}/ser-parking-exemptions`); if no city/zone is selected and an exemption existed when the dialog opened, it SHALL clear the exemption (`DELETE /vehicles/{id}/ser-parking-exemptions`); otherwise no exemption API call is made. There SHALL be no separate "Save exemption" action requiring the user to save the exemption before saving the rest of the vehicle's fields.

#### Scenario: City list loads before zone selection is available
- **WHEN** the vehicle edit flow's exemption picker is opened
- **THEN** the city selector is populated from `GET /cities` and the zone selector has no options until a city is chosen

#### Scenario: Choosing a city loads its SER zones labeled by neighbourhood, alphabetically
- **WHEN** the user selects a city in the picker
- **THEN** the zone selector is populated from `GET /parking/ser-zone-options?city=<selected>&sort=asc`, with each option displaying its `neighbourhood` name in ascending alphabetical order

#### Scenario: A pre-existing selection shows a loading state instead of appearing unselected
- **WHEN** the dialog opens for a vehicle that already has a stored exemption, and the zone options for its city have not finished loading yet
- **THEN** the zone selector shows a distinct loading indicator rather than its normal "select a zone" placeholder, so the already-known selection does not appear to be missing

#### Scenario: Saving persists both the vehicle fields and the exemption in one action
- **WHEN** the user edits the vehicle's display name, selects a city and zone in the picker, and clicks the single "Save" button
- **THEN** the vehicle update is submitted and `POST /vehicles/{id}/ser-parking-exemptions` is called with the selected `city_code` and `zone_number`, in the same submission — no separate "Save exemption" step is required

#### Scenario: Clearing the picker and saving removes the stored exemption
- **WHEN** the user triggers the "Clear" action on a vehicle with a stored exemption (resetting the picker's local selection) and then clicks "Save"
- **THEN** `DELETE /vehicles/{id}/ser-parking-exemptions` is called as part of that save, not before it

#### Scenario: Saving with no exemption selected and none previously stored makes no exemption call
- **WHEN** the user saves a vehicle that never had a stored exemption and never selected one in the picker
- **THEN** neither `POST` nor `DELETE .../ser-parking-exemptions` is called
