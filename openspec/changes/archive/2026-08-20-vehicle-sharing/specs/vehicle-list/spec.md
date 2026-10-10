## MODIFIED Requirements

### Requirement: GET /vehicles returns all vehicles accessible to the authenticated user
The system SHALL expose `GET /vehicles` requiring a valid JWT session cookie. The response SHALL be a JSON array of vehicle objects, each including the vehicle's metadata, its latest known location (if any), whether it has SER tickets, and an `is_owner` boolean. The list SHALL include every vehicle owned by the authenticated user and every vehicle shared with them. Unauthenticated requests SHALL be rejected with HTTP 401.

#### Scenario: Authenticated user with owned vehicles
- **WHEN** an authenticated user sends `GET /vehicles`
- **THEN** the response is HTTP 200 with a JSON array containing one object per vehicle owned by that user, each with `is_owner: true`

#### Scenario: Authenticated user sees vehicles shared with them
- **WHEN** an authenticated user is a sharee of a vehicle owned by another user
- **THEN** the response includes that vehicle with `is_owner: false`

#### Scenario: Vehicle without plate returns null in list
- **WHEN** a vehicle has no license plate set
- **THEN** the `license_plate` field in the list item is `null`

#### Scenario: Authenticated user with no accessible vehicles
- **WHEN** an authenticated user sends `GET /vehicles` and has no owned or shared vehicles
- **THEN** the response is HTTP 200 with an empty JSON array

#### Scenario: Unauthenticated request rejected
- **WHEN** a request is sent to `GET /vehicles` without a session cookie or with an expired JWT
- **THEN** the response is HTTP 401

#### Scenario: User does not see unshared vehicles owned by others
- **WHEN** multiple users have vehicles and none are shared with the authenticated user
- **THEN** `GET /vehicles` returns only the authenticated user's owned vehicles

---

### Requirement: Vehicle list response includes ownership flag
Each item in the `GET /vehicles` response SHALL include an `is_owner` boolean field. It SHALL be `true` if and only if the authenticated user is the vehicle's `owner_id`.

#### Scenario: Owned vehicle marks is_owner true
- **WHEN** a list item represents a vehicle owned by the authenticated user
- **THEN** the item contains `is_owner: true`

#### Scenario: Shared vehicle marks is_owner false
- **WHEN** a list item represents a vehicle shared with the authenticated user
- **THEN** the item contains `is_owner: false`
