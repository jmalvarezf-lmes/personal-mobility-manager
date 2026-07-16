### Requirement: UserPreferences entity represents per-user settings
The system SHALL define a `UserPreferences` domain entity with fields: `user_id` (UUID), `default_ticket_duration_minutes` (int), `auto_create_ticket` (bool), `preferred_notification_channel` (str | None), `notification_language` (str | None), `updated_at` (datetime).

#### Scenario: UserPreferences entity is immutable value object
- **WHEN** a `UserPreferences` is constructed from database fields
- **THEN** it is a frozen dataclass (or equivalent) with all six fields populated

---

### Requirement: user_preferences table persists per-user settings
The system SHALL create a `user_preferences` table with columns: `user_id UUID PRIMARY KEY REFERENCES users(id)`, `default_ticket_duration_minutes INT NOT NULL DEFAULT 60`, `auto_create_ticket BOOLEAN NOT NULL DEFAULT false`, `preferred_notification_channel TEXT NULL`, `notification_language TEXT NULL`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`.

#### Scenario: user_preferences table schema
- **WHEN** the migration is applied
- **THEN** the `user_preferences` table exists with all six columns
- **THEN** `user_id` is both the primary key and a foreign key to `users.id`
- **THEN** `preferred_notification_channel` and `notification_language` both allow `NULL` and default to unset for existing and new rows

---

### Requirement: UserPreferencesRepository provides get and update
The system SHALL define a `UserPreferencesRepository` port with:
- `ensure_default(user_id: UUID) -> None` — inserts a default preferences row for `user_id` if one does not already exist; SHALL NOT modify an existing row
- `find_by_user_id(user_id: UUID) -> UserPreferences | None` — returns the preferences for the given user, or `None` if none exist
- `update(user_id: UUID, default_ticket_duration_minutes: int, auto_create_ticket: bool, preferred_notification_channel: str | None, notification_language: str | None) -> UserPreferences` — replaces all four fields for the user's existing row and returns the persisted `UserPreferences`
- `set_preferred_notification_channel(user_id: UUID, channel: str | None) -> None` — updates only `preferred_notification_channel` for the user's existing row, leaving other fields untouched; used by channel connect/disconnect flows rather than the full-preferences `update` method

#### Scenario: ensure_default creates a row with defaults
- **WHEN** `ensure_default` is called for a `user_id` with no existing preferences row
- **THEN** a new row is inserted with `default_ticket_duration_minutes = 60`, `auto_create_ticket = false`, `preferred_notification_channel = NULL`, and `notification_language = NULL`

#### Scenario: ensure_default is a no-op for an existing row
- **WHEN** `ensure_default` is called for a `user_id` that already has a preferences row with non-default values
- **THEN** the existing row's values are left unchanged

#### Scenario: update replaces all four fields
- **WHEN** `update` is called with new `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, and `notification_language` values for an existing user
- **THEN** all four fields are overwritten and `updated_at` is refreshed
- **THEN** the returned `UserPreferences` reflects the new values

#### Scenario: set_preferred_notification_channel updates only that field
- **WHEN** `set_preferred_notification_channel` is called for an existing user with a channel name
- **THEN** only `preferred_notification_channel` and `updated_at` change
- **THEN** `default_ticket_duration_minutes`, `auto_create_ticket`, and `notification_language` remain unchanged

#### Scenario: set_preferred_notification_channel accepts None to clear the preference
- **WHEN** `set_preferred_notification_channel` is called with `channel=None` for a user with a previously set preference
- **THEN** `preferred_notification_channel` becomes `NULL`

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
The system SHALL expose `GET /preferences`, requiring an authenticated session, returning the current user's `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, and `notification_language`.

#### Scenario: Logged-in user fetches preferences
- **WHEN** an authenticated user sends `GET /preferences`
- **THEN** the response is `200 OK` with their `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, and `notification_language`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `GET /preferences`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Authenticated user can update their preferences
The system SHALL expose `PUT /preferences`, requiring an authenticated session, accepting `default_ticket_duration_minutes` (int, > 0), `auto_create_ticket` (bool), `preferred_notification_channel` (str or null), and `notification_language` (str or null), replacing all four values for the current user. The system SHALL reject a `preferred_notification_channel` value that does not correspond to a channel the current user has configured. The system SHALL likewise reject a `notification_language` value that is not among the system's supported languages; `null` is always accepted and clears the preference.

#### Scenario: Logged-in user updates preferences
- **WHEN** an authenticated user sends `PUT /preferences` with `default_ticket_duration_minutes: 90`, `auto_create_ticket: true`, `preferred_notification_channel: "telegram"` (a channel they have connected), and `notification_language: "es"`
- **THEN** the response is `200 OK` with the updated values
- **THEN** a subsequent `GET /preferences` reflects the new values

#### Scenario: Invalid duration is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `default_ticket_duration_minutes: 0` or a negative number
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Preferred channel not configured by the user is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `preferred_notification_channel` set to a channel they have not connected
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Clearing the preferred channel is allowed
- **WHEN** an authenticated user sends `PUT /preferences` with `preferred_notification_channel: null`
- **THEN** the response is `200 OK` and the user's `preferred_notification_channel` becomes unset

#### Scenario: Unrecognized notification_language value is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `notification_language` set to a value not among the system's supported languages
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Clearing the notification language is allowed
- **WHEN** an authenticated user sends `PUT /preferences` with `notification_language: null`
- **THEN** the response is `200 OK` and the user's `notification_language` becomes unset

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `PUT /preferences`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Preferences page is visible only when logged in
The system SHALL provide a frontend "Preferences" page, reachable only via a protected route, that lets the user view and edit `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, and `notification_language`. The `preferred_notification_channel` control SHALL only offer choices among the channels the user currently has connected (per `GET /notifications/channels`), plus an option to clear the preference. The `notification_language` control SHALL offer the system's supported languages, sourced from `GET /notifications/languages` rather than a hardcoded frontend list, so the offered options and the backend's `PUT /preferences` validation cannot drift apart.

#### Scenario: Logged-out user cannot reach the preferences page
- **WHEN** an unauthenticated visitor navigates to the preferences route
- **THEN** they are redirected away (consistent with other protected routes such as My Vehicles)

#### Scenario: Logged-in user edits and saves preferences
- **WHEN** an authenticated user changes the duration and the auto-create toggle on the preferences page and saves
- **THEN** the page calls `PUT /preferences` with the new values

#### Scenario: Logged-in user picks a preferred notification channel
- **WHEN** an authenticated user with one or more connected notification channels selects one as preferred and saves
- **THEN** the page calls `PUT /preferences` with that channel as `preferred_notification_channel`
- **THEN** the page reflects the saved value on success

#### Scenario: User with no connected channels sees no selectable options
- **WHEN** an authenticated user with no connected notification channels views the preferences page
- **THEN** the preferred-channel control shows no selectable channel options

#### Scenario: Logged-in user picks a notification language
- **WHEN** an authenticated user selects a notification language and saves
- **THEN** the page calls `PUT /preferences` with that value as `notification_language`
- **THEN** the page reflects the saved value on success

#### Scenario: Notification-language options are fetched from the backend catalog
- **WHEN** the preferences page loads
- **THEN** it calls `GET /notifications/languages` and renders the returned languages as the `notification_language` control's options, rather than using a hardcoded list

---

### Requirement: Logged-in navigation exposes an account dropdown
The system SHALL replace the flat logged-in nav links with a dropdown menu triggered by the user's email, containing links to My Vehicles, Preferences, and Logout.

#### Scenario: Logged-in user opens the account dropdown
- **WHEN** an authenticated user clicks their email in the nav
- **THEN** a menu appears with links to My Vehicles and Preferences, and a Logout action

#### Scenario: Logged-out user sees no account dropdown
- **WHEN** an unauthenticated visitor views the nav
- **THEN** no account dropdown, My Vehicles link, or Preferences link is shown
