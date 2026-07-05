## ADDED Requirements

### Requirement: UserPreferences entity represents per-user settings
The system SHALL define a `UserPreferences` domain entity with fields: `user_id` (UUID), `default_ticket_duration_minutes` (int), `auto_create_ticket` (bool), `updated_at` (datetime).

#### Scenario: UserPreferences entity is immutable value object
- **WHEN** a `UserPreferences` is constructed from database fields
- **THEN** it is a frozen dataclass (or equivalent) with all four fields populated

---

### Requirement: user_preferences table persists per-user settings
The system SHALL create a `user_preferences` table with columns: `user_id UUID PRIMARY KEY REFERENCES users(id)`, `default_ticket_duration_minutes INT NOT NULL DEFAULT 60`, `auto_create_ticket BOOLEAN NOT NULL DEFAULT false`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`.

#### Scenario: user_preferences table schema
- **WHEN** the migration is applied
- **THEN** the `user_preferences` table exists with all four columns
- **THEN** `user_id` is both the primary key and a foreign key to `users.id`

---

### Requirement: UserPreferencesRepository provides get and update
The system SHALL define a `UserPreferencesRepository` port with:
- `ensure_default(user_id: UUID) -> None` — inserts a default preferences row for `user_id` if one does not already exist; SHALL NOT modify an existing row
- `find_by_user_id(user_id: UUID) -> UserPreferences | None` — returns the preferences for the given user, or `None` if none exist
- `update(user_id: UUID, default_ticket_duration_minutes: int, auto_create_ticket: bool) -> UserPreferences` — replaces both fields for the user's existing row and returns the persisted `UserPreferences`

#### Scenario: ensure_default creates a row with defaults
- **WHEN** `ensure_default` is called for a `user_id` with no existing preferences row
- **THEN** a new row is inserted with `default_ticket_duration_minutes = 60` and `auto_create_ticket = false`

#### Scenario: ensure_default is a no-op for an existing row
- **WHEN** `ensure_default` is called for a `user_id` that already has a preferences row with non-default values
- **THEN** the existing row's values are left unchanged

#### Scenario: update replaces both fields
- **WHEN** `update` is called with new `default_ticket_duration_minutes` and `auto_create_ticket` values for an existing user
- **THEN** both fields are overwritten and `updated_at` is refreshed
- **THEN** the returned `UserPreferences` reflects the new values

---

### Requirement: Login provisions default preferences for the user
The system SHALL call `ensure_default` for the authenticated user's `id` as part of the Google login flow (`authenticate_google_user`), immediately after the `users` upsert, so every user has a preferences row by the time they can access the preferences page. The two writes SHALL each be individually atomic and idempotent (`ensure_default` uses `ON CONFLICT DO NOTHING`); they are not required to share a single database transaction, since a failure between them leaves a user temporarily without a preferences row until their next login, which self-heals it — no partial or inconsistent state persists.

#### Scenario: First login for a new user creates preferences
- **WHEN** a user logs in via Google for the first time
- **THEN** a `users` row is created
- **THEN** a `user_preferences` row is created for that user with default values

#### Scenario: Login for an existing user without preferences backfills them
- **WHEN** a user who already has a `users` row (created before this change) logs in
- **THEN** a `user_preferences` row is created for that user with default values if none existed

#### Scenario: Login for a user with existing preferences does not alter them
- **WHEN** a user with a `user_preferences` row already set to non-default values logs in
- **THEN** their preferences values are unchanged after login

---

### Requirement: Authenticated user can read their preferences
The system SHALL expose `GET /preferences`, requiring an authenticated session, returning the current user's `default_ticket_duration_minutes` and `auto_create_ticket`.

#### Scenario: Logged-in user fetches preferences
- **WHEN** an authenticated user sends `GET /preferences`
- **THEN** the response is `200 OK` with their `default_ticket_duration_minutes` and `auto_create_ticket`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `GET /preferences`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Authenticated user can update their preferences
The system SHALL expose `PUT /preferences`, requiring an authenticated session, accepting `default_ticket_duration_minutes` (int, > 0) and `auto_create_ticket` (bool), replacing both values for the current user.

#### Scenario: Logged-in user updates preferences
- **WHEN** an authenticated user sends `PUT /preferences` with `default_ticket_duration_minutes: 90` and `auto_create_ticket: true`
- **THEN** the response is `200 OK` with the updated values
- **THEN** a subsequent `GET /preferences` reflects the new values

#### Scenario: Invalid duration is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `default_ticket_duration_minutes: 0` or a negative number
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `PUT /preferences`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Preferences page is visible only when logged in
The system SHALL provide a frontend "Preferences" page, reachable only via a protected route, that lets the user view and edit `default_ticket_duration_minutes` and `auto_create_ticket`.

#### Scenario: Logged-out user cannot reach the preferences page
- **WHEN** an unauthenticated visitor navigates to the preferences route
- **THEN** they are redirected away (consistent with other protected routes such as My Vehicles)

#### Scenario: Logged-in user edits and saves preferences
- **WHEN** an authenticated user changes the duration and the auto-create toggle on the preferences page and saves
- **THEN** the page calls `PUT /preferences` with the new values
- **THEN** the page reflects the saved values on success

---

### Requirement: Logged-in navigation exposes an account dropdown
The system SHALL replace the flat logged-in nav links with a dropdown menu triggered by the user's email, containing links to My Vehicles, Preferences, and Logout.

#### Scenario: Logged-in user opens the account dropdown
- **WHEN** an authenticated user clicks their email in the nav
- **THEN** a menu appears with links to My Vehicles and Preferences, and a Logout action

#### Scenario: Logged-out user sees no account dropdown
- **WHEN** an unauthenticated visitor views the nav
- **THEN** no account dropdown, My Vehicles link, or Preferences link is shown
