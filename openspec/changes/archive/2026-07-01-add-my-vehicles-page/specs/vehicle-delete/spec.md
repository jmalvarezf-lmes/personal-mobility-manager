## ADDED Requirements

### Requirement: DELETE /vehicles/{id} removes a vehicle and its associated data
The system SHALL expose `DELETE /vehicles/{id}` requiring a valid JWT session cookie. On success, the vehicle row SHALL be deleted; the associated `vehicle_configs` and `vehicle_locations` rows SHALL be removed automatically via `ON DELETE CASCADE` database constraints. Unauthenticated requests SHALL return HTTP 401. Requests for a vehicle not owned by the authenticated user SHALL return HTTP 403. Requests for a non-existent vehicle SHALL return HTTP 404. A successful delete SHALL return HTTP 204 No Content.

#### Scenario: Owner deletes their vehicle
- **WHEN** an authenticated user sends `DELETE /vehicles/{id}` for a vehicle they own
- **THEN** the response is HTTP 204
- **THEN** the vehicle row no longer exists in the database
- **THEN** all `vehicle_configs` rows for that vehicle_id are gone (cascade)
- **THEN** all `vehicle_locations` rows for that vehicle_id are gone (cascade)

#### Scenario: Non-owner delete rejected
- **WHEN** an authenticated user sends `DELETE /vehicles/{id}` for a vehicle owned by a different user
- **THEN** the response is HTTP 403 and the vehicle is not deleted

#### Scenario: Non-existent vehicle returns 404
- **WHEN** an authenticated user sends `DELETE /vehicles/{id}` with an unknown UUID
- **THEN** the response is HTTP 404

#### Scenario: Subsequent GET after delete returns 404
- **WHEN** a vehicle is successfully deleted
- **THEN** `GET /vehicles/{id}` for the same id returns HTTP 404
