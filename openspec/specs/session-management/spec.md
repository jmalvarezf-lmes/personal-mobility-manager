## ADDED Requirements

### Requirement: A session record is created on every successful login
On a successful Google OAuth callback, the system SHALL create a `sessions` row with a newly generated `id` (UUID), the authenticated user's `id`, `created_at` set to the current time, `expires_at` set to 24 hours from creation, and `revoked_at` set to `NULL`.

#### Scenario: Session row is created on login
- **WHEN** a user completes the Google OAuth2 callback successfully
- **THEN** a new row is inserted into `sessions` with a fresh `id`, the user's `id`, and `revoked_at = NULL`

#### Scenario: Repeated logins create independent sessions
- **WHEN** the same user logs in twice (e.g., from two devices)
- **THEN** two distinct `sessions` rows exist, each with its own `id`, both `revoked_at = NULL`

---

### Requirement: A session is revoked (not deleted) on logout
On `POST /auth/logout`, if the request carries a valid, decodable session cookie, the system SHALL set `revoked_at` to the current time on the corresponding `sessions` row. The row SHALL NOT be deleted.

#### Scenario: Logout revokes the session
- **WHEN** a client sends `POST /auth/logout` with a valid session cookie
- **THEN** the corresponding `sessions` row has `revoked_at` set to the current time
- **THEN** the row still exists in the `sessions` table

#### Scenario: Logout with no cookie does not error
- **WHEN** a client sends `POST /auth/logout` with no session cookie, or a cookie that fails to decode
- **THEN** the system still responds with HTTP 204 and performs no session revocation

---

### Requirement: Session validity requires an existing, non-revoked, non-expired, owner-matching row
Given a session id (`sid`) and user id (`sub`) extracted from a validated JWT, the system SHALL treat the session as valid only if: a `sessions` row with that `id` exists, its `revoked_at` is `NULL`, its `expires_at` is in the future, and its `user_id` equals `sub`. Any other outcome SHALL be treated as invalid.

#### Scenario: Live session is valid
- **WHEN** the session row exists, `revoked_at IS NULL`, `expires_at` is in the future, and `user_id` matches the JWT's `sub`
- **THEN** the session is considered valid

#### Scenario: Revoked session is invalid
- **WHEN** the session row exists but `revoked_at` is set
- **THEN** the session is considered invalid

#### Scenario: Unknown session id is invalid
- **WHEN** no `sessions` row exists with the given `id`
- **THEN** the session is considered invalid

#### Scenario: Expired session row is invalid
- **WHEN** the session row's `expires_at` is in the past
- **THEN** the session is considered invalid

#### Scenario: Session/user mismatch is invalid
- **WHEN** the session row's `user_id` does not equal the JWT's `sub` claim
- **THEN** the session is considered invalid

---

### Requirement: Expired and revoked sessions are purged after a configurable retention window
The system SHALL run a scheduled job that deletes `sessions` rows where either `revoked_at` or `expires_at` is older than `SESSION_CLEANUP_RETENTION_DAYS` (default 30 days) before the current time. The job SHALL run on an interval controlled by `SESSION_CLEANUP_INTERVAL_HOURS` (default 24 hours). Both values SHALL be configurable via environment variables.

#### Scenario: Old revoked session is purged
- **WHEN** the cleanup job runs and a session's `revoked_at` is older than the configured retention window
- **THEN** that row is deleted from `sessions`

#### Scenario: Old expired-but-never-revoked session is purged
- **WHEN** the cleanup job runs and a session's `expires_at` is older than the configured retention window, even if `revoked_at IS NULL`
- **THEN** that row is deleted from `sessions`

#### Scenario: Recent session is not purged
- **WHEN** the cleanup job runs and a session's `expires_at` and `revoked_at` (if set) are both within the retention window
- **THEN** that row is left untouched

#### Scenario: Retention window is configurable
- **WHEN** `SESSION_CLEANUP_RETENTION_DAYS` is set to a custom value
- **THEN** the cleanup job uses that value instead of the default 30 days
