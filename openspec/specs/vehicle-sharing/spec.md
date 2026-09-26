## Purpose

Allow a vehicle owner to grant read and notification access to other registered users while keeping all write and destructive operations exclusive to the owner.

## Requirements

### Requirement: VehicleShare entity represents a share grant
The system SHALL define a `VehicleShare` domain entity with fields `vehicle_id` (UUID), `user_id` (UUID), and `created_at` (datetime). The combination of `(vehicle_id, user_id)` SHALL uniquely identify a share.

#### Scenario: Entity fields are immutable
- **WHEN** a `VehicleShare` is instantiated
- **THEN** its `vehicle_id`, `user_id`, and `created_at` fields are set and cannot be mutated

---

### Requirement: VehicleShareRepository port provides share persistence
The system SHALL define a `VehicleShareRepository` abstract port with at minimum:
- `save(share: VehicleShare) -> None`
- `find_by_vehicle_and_user(vehicle_id: UUID, user_id: UUID) -> VehicleShare | None`
- `list_sharees(vehicle_id: UUID) -> list[VehicleShare]`
- `delete(vehicle_id: UUID, user_id: UUID) -> None`
- `list_vehicle_ids_for_user(user_id: UUID) -> list[UUID]`

`delete` SHALL be idempotent — deleting a non-existent share SHALL NOT raise.

#### Scenario: Save creates a share
- **WHEN** `save` is called with a `VehicleShare`
- **THEN** a row is inserted into `vehicle_shares`

#### Scenario: Duplicate save is idempotent
- **WHEN** `save` is called for a `(vehicle_id, user_id)` pair that already exists
- **THEN** no duplicate row is created and no error is raised

#### Scenario: Delete removes a share
- **WHEN** `delete` is called for an existing `(vehicle_id, user_id)` pair
- **THEN** the row is removed

#### Scenario: Delete is idempotent for missing share
- **WHEN** `delete` is called for a `(vehicle_id, user_id)` pair that does not exist
- **THEN** it completes without raising

---

### Requirement: POST /vehicles/{id}/shares grants access to an existing user by email
The system SHALL expose `POST /vehicles/{id}/shares` requiring a valid JWT session cookie. The request body SHALL contain `{ "email": string }`. The endpoint SHALL be restricted to the vehicle's owner. If no user exists with the given email, the system SHALL respond with HTTP 404 with a generic "Vehicle or user not found" message to avoid email enumeration. If the requested email belongs to the owner themselves, the system SHALL respond with HTTP 422. If the vehicle is already shared with that user, the system SHALL respond with HTTP 201 without creating a duplicate. On success, the system SHALL create a `VehicleShare` row and respond with HTTP 201 containing the full list of sharees, each with `user_id`, `display_name`, `email`, and `created_at`.

#### Scenario: Owner shares vehicle with another registered user
- **WHEN** the owner sends `POST /vehicles/{id}/shares` with the email of another registered user
- **THEN** the response is HTTP 201 with a `sharees` array containing the new sharee's `user_id`, `display_name`, `email`, and `created_at`
- **THEN** a `VehicleShare` row exists for `(vehicle_id, sharee_user_id)`

#### Scenario: Sharing with unknown email is rejected
- **WHEN** the owner sends `POST /vehicles/{id}/shares` with an email not present in `users`
- **THEN** the response is HTTP 404

#### Scenario: Owner cannot share with themselves
- **WHEN** the owner sends `POST /vehicles/{id}/shares` with their own email
- **THEN** the response is HTTP 422 and no share row is created

#### Scenario: Re-sharing the same user is idempotent
- **WHEN** the owner sends `POST /vehicles/{id}/shares` with an email already shared
- **THEN** the response is HTTP 201 with a `sharees` array containing the existing sharee and no duplicate share row is created

#### Scenario: Sharee cannot add sharees
- **WHEN** a sharee sends `POST /vehicles/{id}/shares`
- **THEN** the response is HTTP 403

#### Scenario: Unauthenticated sharing is rejected
- **WHEN** a request is sent to `POST /vehicles/{id}/shares` without a valid session cookie
- **THEN** the response is HTTP 401

---

### Requirement: GET /vehicles/{id}/shares lists current sharees
The system SHALL expose `GET /vehicles/{id}/shares` requiring a valid JWT session cookie. The endpoint SHALL be restricted to the vehicle's owner. The response SHALL be HTTP 200 with a JSON array of objects containing each sharee's `user_id`, `display_name`, `email`, and `created_at`.

#### Scenario: Owner lists sharees
- **WHEN** the owner sends `GET /vehicles/{id}/shares` for a vehicle shared with two users
- **THEN** the response is HTTP 200 with an array of two sharee objects

#### Scenario: Sharee cannot list sharees
- **WHEN** a sharee sends `GET /vehicles/{id}/shares`
- **THEN** the response is HTTP 403

#### Scenario: Empty share list
- **WHEN** the owner sends `GET /vehicles/{id}/shares` for a vehicle with no sharees
- **THEN** the response is HTTP 200 with an empty array

---

### Requirement: DELETE /vehicles/{id}/shares/{user_id} revokes a share
The system SHALL expose `DELETE /vehicles/{id}/shares/{user_id}` requiring a valid JWT session cookie. The endpoint SHALL accept the call if the authenticated user is the vehicle's owner or if the authenticated user's id matches `{user_id}` (self-revoke by the sharee). Requests for a non-existent vehicle SHALL return HTTP 404. On success the system SHALL delete the share row and respond with HTTP 204.

#### Scenario: Owner revokes a share
- **WHEN** the owner sends `DELETE /vehicles/{id}/shares/{sharee_user_id}`
- **THEN** the response is HTTP 204 and the share row is removed

#### Scenario: Sharee revokes their own access
- **WHEN** a sharee sends `DELETE /vehicles/{id}/shares/{their_own_user_id}`
- **THEN** the response is HTTP 204 and their share row is removed

#### Scenario: Sharee cannot revoke another sharee
- **WHEN** sharee A sends `DELETE /vehicles/{id}/shares/{sharee_b_user_id}`
- **THEN** the response is HTTP 403

#### Scenario: Revoking a non-existent share is idempotent
- **WHEN** the owner sends `DELETE /vehicles/{id}/shares/{user_id}` for a user who is not a sharee
- **THEN** the response is HTTP 204
