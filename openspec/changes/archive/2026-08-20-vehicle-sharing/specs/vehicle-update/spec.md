## MODIFIED Requirements

### Requirement: PUT /vehicles/{id} updates vehicle display_name, license_plate, and brand-specific credentials
The system SHALL expose `PUT /vehicles/{id}` requiring a valid JWT session cookie. The request body SHALL be a discriminated union by brand, with all brand variants inheriting from a `BaseUpdateVehicleRequest` that includes `display_name` and `license_plate` (optional, max 20 chars). `display_name` is always updatable. `license_plate` is always updatable for all brands (set to string value or `null` to clear). For Toyota: `username` and `locale` are required; `password` is optional (omitted or empty string means keep the existing encrypted password). For Generic: only `display_name` and `license_plate` are updatable. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle not owned by the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404.

#### Scenario: Update Toyota display_name only
- **WHEN** an authenticated owner sends `PUT /vehicles/{id}` for a Toyota vehicle with a new `display_name`, empty `password`, and no `license_plate`
- **THEN** the vehicle's `display_name` is updated in the database
- **THEN** the Toyota credentials (username, password, locale) are unchanged
- **THEN** the `license_plate` is unchanged

#### Scenario: Update Generic display_name
- **WHEN** an authenticated owner sends `PUT /vehicles/{id}` for a Generic vehicle with a new `display_name`
- **THEN** the vehicle's `display_name` is updated
- **THEN** the `location_token` is unchanged

#### Scenario: Sharee update rejected
- **WHEN** an authenticated user sends `PUT /vehicles/{id}` for a vehicle shared with them but not owned by them
- **THEN** the response is HTTP 403 and the vehicle is not updated

#### Scenario: Non-existent vehicle returns 404
- **WHEN** an authenticated user sends `PUT /vehicles/{id}` with an unknown UUID
- **THEN** the response is HTTP 404

#### Scenario: Successful update returns updated vehicle
- **WHEN** `PUT /vehicles/{id}` succeeds
- **THEN** the response is HTTP 200 with the updated vehicle object (same shape as GET /vehicles/{id}), including the updated `license_plate`
