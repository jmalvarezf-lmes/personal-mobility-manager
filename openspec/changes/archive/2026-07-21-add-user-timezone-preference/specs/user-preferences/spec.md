## MODIFIED Requirements

### Requirement: UserPreferences entity represents per-user settings
The system SHALL define a `UserPreferences` domain entity with fields: `user_id` (UUID), `default_ticket_duration_minutes` (int), `auto_create_ticket` (bool), `preferred_notification_channel` (str | None), `notification_language` (str | None), `timezone` (str | None), `updated_at` (datetime).

#### Scenario: UserPreferences entity is immutable value object
- **WHEN** a `UserPreferences` is constructed from database fields
- **THEN** it is a frozen dataclass (or equivalent) with all seven fields populated

---

### Requirement: user_preferences table persists per-user settings
The system SHALL create a `user_preferences` table with columns: `user_id UUID PRIMARY KEY REFERENCES users(id)`, `default_ticket_duration_minutes INT NOT NULL DEFAULT 60`, `auto_create_ticket BOOLEAN NOT NULL DEFAULT false`, `preferred_notification_channel TEXT NULL`, `notification_language TEXT NULL`, `timezone TEXT NULL`, `updated_at TIMESTAMP WITH TIME ZONE NOT NULL`.

#### Scenario: user_preferences table schema
- **WHEN** the migration is applied
- **THEN** the `user_preferences` table exists with all seven columns
- **THEN** `user_id` is both the primary key and a foreign key to `users.id`
- **THEN** `preferred_notification_channel`, `notification_language`, and `timezone` all allow `NULL` and default to unset for existing and new rows

---

### Requirement: UserPreferencesRepository provides get and update
The system SHALL define a `UserPreferencesRepository` port with:
- `ensure_default(user_id: UUID) -> None` — inserts a default preferences row for `user_id` if one does not already exist; SHALL NOT modify an existing row
- `find_by_user_id(user_id: UUID) -> UserPreferences | None` — returns the preferences for the given user, or `None` if none exist
- `update(user_id: UUID, default_ticket_duration_minutes: int, auto_create_ticket: bool, preferred_notification_channel: str | None, notification_language: str | None, timezone: str | None) -> UserPreferences` — replaces all five fields for the user's existing row and returns the persisted `UserPreferences`
- `set_preferred_notification_channel(user_id: UUID, channel: str | None) -> None` — updates only `preferred_notification_channel` for the user's existing row, leaving other fields untouched; used by channel connect/disconnect flows rather than the full-preferences `update` method

#### Scenario: ensure_default creates a row with defaults
- **WHEN** `ensure_default` is called for a `user_id` with no existing preferences row
- **THEN** a new row is inserted with `default_ticket_duration_minutes = 60`, `auto_create_ticket = false`, `preferred_notification_channel = NULL`, `notification_language = NULL`, and `timezone = NULL`

#### Scenario: ensure_default is a no-op for an existing row
- **WHEN** `ensure_default` is called for a `user_id` that already has a preferences row with non-default values
- **THEN** the existing row's values are left unchanged

#### Scenario: update replaces all five fields
- **WHEN** `update` is called with new `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, `notification_language`, and `timezone` values for an existing user
- **THEN** all five fields are overwritten and `updated_at` is refreshed
- **THEN** the returned `UserPreferences` reflects the new values

#### Scenario: set_preferred_notification_channel updates only that field
- **WHEN** `set_preferred_notification_channel` is called for an existing user with a channel name
- **THEN** only `preferred_notification_channel` and `updated_at` change
- **THEN** `default_ticket_duration_minutes`, `auto_create_ticket`, `notification_language`, and `timezone` remain unchanged

#### Scenario: set_preferred_notification_channel accepts None to clear the preference
- **WHEN** `set_preferred_notification_channel` is called with `channel=None` for a user with a previously set preference
- **THEN** `preferred_notification_channel` becomes `NULL`

---

### Requirement: Authenticated user can read their preferences
The system SHALL expose `GET /preferences`, requiring an authenticated session, returning the current user's `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, `notification_language`, and `timezone`.

#### Scenario: Logged-in user fetches preferences
- **WHEN** an authenticated user sends `GET /preferences`
- **THEN** the response is `200 OK` with their `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, `notification_language`, and `timezone`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `GET /preferences`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Authenticated user can update their preferences
The system SHALL expose `PUT /preferences`, requiring an authenticated session, accepting `default_ticket_duration_minutes` (int, > 0), `auto_create_ticket` (bool), `preferred_notification_channel` (str or null), `notification_language` (str or null), and `timezone` (str or null), replacing all five values for the current user. The system SHALL reject a `preferred_notification_channel` value that does not correspond to a channel the current user has configured. The system SHALL reject a `notification_language` value that is not among the system's supported languages. The system SHALL reject a `timezone` value that is not a recognized IANA timezone identifier (validated against `zoneinfo.available_timezones()`). `null` is always accepted for `preferred_notification_channel`, `notification_language`, and `timezone`, and clears the corresponding preference.

#### Scenario: Logged-in user updates preferences
- **WHEN** an authenticated user sends `PUT /preferences` with `default_ticket_duration_minutes: 90`, `auto_create_ticket: true`, `preferred_notification_channel: "telegram"` (a channel they have connected), `notification_language: "es"`, and `timezone: "Europe/Madrid"`
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

#### Scenario: Unrecognized timezone value is rejected
- **WHEN** an authenticated user sends `PUT /preferences` with `timezone` set to a string that is not a recognized IANA timezone identifier
- **THEN** the response is `422 Unprocessable Entity` and no values are changed

#### Scenario: Valid timezone is accepted
- **WHEN** an authenticated user sends `PUT /preferences` with `timezone: "Europe/Madrid"`
- **THEN** the response is `200 OK` and the user's `timezone` becomes `"Europe/Madrid"`

#### Scenario: Clearing the timezone is allowed
- **WHEN** an authenticated user sends `PUT /preferences` with `timezone: null`
- **THEN** the response is `200 OK` and the user's `timezone` becomes unset

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `PUT /preferences`
- **THEN** the response is `401 Unauthorized`

---

### Requirement: Preferences page is visible only when logged in
The system SHALL provide a frontend "Preferences" page, reachable only via a protected route, that lets the user view and edit `default_ticket_duration_minutes`, `auto_create_ticket`, `preferred_notification_channel`, `notification_language`, and `timezone`. The `preferred_notification_channel` control SHALL only offer choices among the channels the user currently has connected (per `GET /notifications/channels`), plus an option to clear the preference. The `notification_language` control SHALL offer the system's supported languages, sourced from `GET /notifications/languages` rather than a hardcoded frontend list, so the offered options and the backend's `PUT /preferences` validation cannot drift apart. The `timezone` control SHALL be a searchable picker listing every IANA zone returned by `Intl.supportedValuesOf('timeZone')`, each labeled with its zone name and current UTC offset/abbreviation (e.g. "Europe/Madrid (CEST)"), plus an option to clear the preference back to unset.

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

#### Scenario: Logged-in user picks a timezone
- **WHEN** an authenticated user searches for and selects a timezone (e.g. by typing "Madrid") and saves
- **THEN** the page calls `PUT /preferences` with that zone's IANA identifier as `timezone`
- **THEN** the page reflects the saved value on success

#### Scenario: Logged-in user clears their timezone preference
- **WHEN** an authenticated user clears the timezone control and saves
- **THEN** the page calls `PUT /preferences` with `timezone: null`

---

## ADDED Requirements

### Requirement: Timezone picker options are city-searchable and DST-aware
The timezone picker on the Preferences page SHALL let the user filter the full IANA zone list by typing part of a zone or city name (e.g. "Madrid" matches `Europe/Madrid`). Each option's displayed abbreviation SHALL be computed against the current date at render time, not a hardcoded or cached value, so it reflects whichever offset (standard or daylight saving) currently applies to that zone.

#### Scenario: Searching filters the zone list
- **WHEN** a user types "Madrid" into the timezone control
- **THEN** the option list narrows to zones whose identifier contains "Madrid" (e.g. `Europe/Madrid`)

#### Scenario: Abbreviation reflects the current DST state
- **WHEN** the timezone picker renders the `Europe/Madrid` option during daylight saving time
- **THEN** the displayed label shows the "CEST" abbreviation, not "CET"
