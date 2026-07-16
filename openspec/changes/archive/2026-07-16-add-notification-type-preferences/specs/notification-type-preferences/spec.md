## ADDED Requirements

### Requirement: notification_types catalog table
The system SHALL define a `notification_types` table with columns `key TEXT PRIMARY KEY`, `label TEXT NOT NULL`, `config_schema JSONB NOT NULL`, seeded via migration with exactly two rows: `location_moved` (label "Vehicle moved") and `ser_zone_ticket_required` (label "SER ticket required"), both with `config_schema = {"threshold_m": {"type": "integer", "min": 1}}`.

#### Scenario: Catalog seeded on migration
- **WHEN** the seeding migration is applied
- **THEN** `notification_types` contains exactly `location_moved` and `ser_zone_ticket_required`, each with a `label` and a `config_schema` declaring `threshold_m`

### Requirement: user_notification_preferences table persists per-user, per-type settings
The system SHALL define a `user_notification_preferences` table with columns `user_id UUID REFERENCES users(id)`, `type_key TEXT REFERENCES notification_types(key)`, `enabled BOOLEAN NOT NULL`, `config JSONB NOT NULL DEFAULT '{}'`, `updated_at TIMESTAMPTZ NOT NULL`, with composite primary key `(user_id, type_key)`.

#### Scenario: user_notification_preferences table schema
- **WHEN** the migration is applied
- **THEN** the `user_notification_preferences` table exists with all five columns and a composite primary key on `(user_id, type_key)`
- **THEN** `type_key` is a foreign key to `notification_types.key`

### Requirement: Existing users are backfilled with disabled preferences
The system SHALL, via a data migration run once at deploy time, insert a `user_notification_preferences` row for every existing `users` row × every `notification_types` row, with `enabled=false, config={}`. This is an explicit opt-in migration: it does not carry forward the prior unconditional-notification behavior, since no user had ever previously consented to either notification kind per type.

#### Scenario: Backfill migration disables all types for all existing users
- **WHEN** the backfill migration runs against a database with existing `users` rows and no `user_notification_preferences` rows
- **THEN** every existing user has exactly one row per `notification_types` entry, each `enabled=false, config={}`

#### Scenario: Backfill is idempotent
- **WHEN** the backfill migration runs a second time (e.g. re-run after a partial failure)
- **THEN** no existing `user_notification_preferences` row is duplicated or overwritten

### Requirement: NotificationPreferencesRepository provides catalog-aware access
The system SHALL define a `NotificationPreferencesRepository` port with:
- `list_types() -> list[NotificationType]` — returns every row in `notification_types`
- `ensure_defaults(user_id: UUID) -> None` — for every `notification_types` row without a matching `(user_id, type_key)` row, inserts `enabled=false, config={}` (opt-in: a user is never auto-enrolled into a notification type); SHALL NOT modify an existing row
- `find_by_user_id(user_id: UUID) -> list[UserNotificationPreference]` — returns the user's preference rows, one per type they have a row for
- `update(user_id: UUID, type_key: str, enabled: bool, config: dict) -> UserNotificationPreference` — replaces `enabled` and `config` for the user's existing `(user_id, type_key)` row (inserting one first via `ensure_defaults` semantics if absent) and returns the persisted value

#### Scenario: ensure_defaults backfills missing types only
- **WHEN** `ensure_defaults` is called for a user who already has a row for `location_moved` but not `ser_zone_ticket_required`
- **THEN** a new `ser_zone_ticket_required` row is inserted with `enabled=false, config={}`
- **THEN** the existing `location_moved` row is left unchanged

#### Scenario: update overwrites enabled and config for one type
- **WHEN** `update` is called for a user's `location_moved` row with `enabled=false, config={"threshold_m": 20}`
- **THEN** only that user's `location_moved` row changes; other types' rows for that user are unaffected

### Requirement: Login provisions default notification preferences
The system SHALL call `NotificationPreferencesRepository.ensure_defaults` for the authenticated user's `id` as part of the Google login flow, alongside the existing `UserPreferencesRepository.ensure_default` call, so every user has a preference row for every catalog type by the time they can access notification settings. Provisioned rows SHALL always start `enabled=false`: a user is never automatically opted into a notification type, including on their very first login.

#### Scenario: First login for a new user creates notification preferences
- **WHEN** a user logs in via Google for the first time
- **THEN** a `user_notification_preferences` row is created for that user for each row in `notification_types`, each `enabled=false, config={}`

#### Scenario: A new notification type backfills for existing users on next login
- **WHEN** a `notification_types` row is added after a user already has notification preference rows for the prior types
- **THEN** that user's next login creates a row for the new type with `enabled=false, config={}`, leaving their existing rows unchanged

### Requirement: Authenticated user can list notification types
The system SHALL expose `GET /notifications/types`, requiring an authenticated session, returning every row from `notification_types` (`key`, `label`, `config_schema`).

#### Scenario: Logged-in user lists notification types
- **WHEN** an authenticated user sends `GET /notifications/types`
- **THEN** the response is `200 OK` with the full catalog, including `location_moved` and `ser_zone_ticket_required`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `GET /notifications/types`
- **THEN** the response is `401 Unauthorized`

### Requirement: Authenticated user can read their notification preferences
The system SHALL expose `GET /notifications/preferences`, requiring an authenticated session, returning the current user's preference for every catalog type: `type_key`, `enabled`, and `config` merged with the type's default (an absent `config` key falls back to the type's fallback value, e.g. `threshold_m` resolves via `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` when not explicitly set).

#### Scenario: Logged-in user fetches notification preferences
- **WHEN** an authenticated user sends `GET /notifications/preferences`
- **THEN** the response is `200 OK` with one entry per catalog type, each including `type_key`, `enabled`, and an effective `config`

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `GET /notifications/preferences`
- **THEN** the response is `401 Unauthorized`

### Requirement: Authenticated user can update a single notification type's preference
The system SHALL expose `PUT /notifications/preferences/{type_key}`, requiring an authenticated session, accepting `enabled` (bool) and `config` (object), replacing both fields for that user's `(user_id, type_key)` row. The system SHALL reject a `type_key` not present in `notification_types`, and SHALL reject a `config` that does not conform to that type's `config_schema`.

#### Scenario: Logged-in user disables a notification type
- **WHEN** an authenticated user sends `PUT /notifications/preferences/ser_zone_ticket_required` with `enabled: false, config: {}`
- **THEN** the response is `200 OK`
- **THEN** a subsequent `GET /notifications/preferences` shows `ser_zone_ticket_required` as `enabled: false`

#### Scenario: Logged-in user customizes a threshold
- **WHEN** an authenticated user sends `PUT /notifications/preferences/location_moved` with `enabled: true, config: {"threshold_m": 20}`
- **THEN** the response is `200 OK` with `config.threshold_m` equal to `20`
- **THEN** a subsequent `GET /notifications/preferences` reflects `threshold_m: 20` for `location_moved`

#### Scenario: Unknown type_key is rejected
- **WHEN** an authenticated user sends `PUT /notifications/preferences/unknown_type`
- **THEN** the response is `404 Not Found` and no row is created or changed

#### Scenario: Config failing the type's schema is rejected
- **WHEN** an authenticated user sends `PUT /notifications/preferences/location_moved` with `config: {"threshold_m": -5}`
- **THEN** the response is `422 Unprocessable Entity` and the existing row is unchanged

#### Scenario: Anonymous request is rejected
- **WHEN** a request without a valid session cookie sends `PUT /notifications/preferences/{type_key}`
- **THEN** the response is `401 Unauthorized`

### Requirement: DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS is the fallback threshold
The system SHALL read `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` from the environment (defaulting to `50` when unset) and use it wherever a user's `config` for a `threshold_m`-bearing type does not specify that key — both when computing the effective config returned by `GET /notifications/preferences` and when either notification handler resolves the threshold to apply at runtime. Newly inserted preference rows (via `ensure_defaults` or migration backfill) SHALL store `config={}` rather than snapshotting this value, so changing the env var takes effect immediately for every user who has not explicitly overridden `threshold_m` for that type. This applies regardless of `enabled`: a disabled row's `config` still resolves through this same fallback the moment the user enables it, so they see the current systemwide default rather than an empty or stale value.

#### Scenario: Default applies when a user has not customized threshold_m
- **WHEN** a user's `location_moved` row has `config={}`
- **THEN** the effective `threshold_m` used is the current value of `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`

#### Scenario: Per-user override takes precedence over the default
- **WHEN** a user's `location_moved` row has `config={"threshold_m": 20}`
- **THEN** the effective `threshold_m` used is `20`, regardless of the current `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` value

### Requirement: Preferences page exposes a Notifications section
The system SHALL extend the frontend Preferences page (protected route) with a "Notifications" section listing every type from `GET /notifications/types`, each rendered as a toggle reflecting `GET /notifications/preferences`. When a type is enabled and its `config_schema` declares a field, the section SHALL render an inline control for that field (e.g. a numeric input for `threshold_m`) and save changes via `PUT /notifications/preferences/{type_key}`.

#### Scenario: Logged-in user toggles a notification type off
- **WHEN** an authenticated user disables `ser_zone_ticket_required` on the Notifications section and saves
- **THEN** the page calls `PUT /notifications/preferences/ser_zone_ticket_required` with `enabled: false`

#### Scenario: Logged-in user edits a type's threshold
- **WHEN** an authenticated user changes the `threshold_m` value shown for `location_moved` (enabled) and saves
- **THEN** the page calls `PUT /notifications/preferences/location_moved` with `config: {"threshold_m": <new value>}`

#### Scenario: Config control hidden for a disabled type
- **WHEN** a type is toggled off
- **THEN** its inline config control (e.g. the threshold input) is not shown
