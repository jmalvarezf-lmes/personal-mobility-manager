## MODIFIED Requirements

### Requirement: notification_types catalog table
The system SHALL define a `notification_types` table with columns `key TEXT PRIMARY KEY`, `label TEXT NOT NULL`, `config_schema JSONB NOT NULL`, seeded via migration with exactly four rows: `location_moved` (label "Vehicle moved"), `ser_zone_ticket_required` (label "SER ticket required"), `ser_ticket_created` (label "SER ticket created"), and `ser_ticket_creation_failed` (label "SER ticket creation failed"). `location_moved` and `ser_zone_ticket_required` have `config_schema = {"threshold_m": {"type": "integer", "min": 1}}`; `ser_ticket_created` and `ser_ticket_creation_failed` have `config_schema = {}` — they react to an event rather than gating on movement distance.

#### Scenario: Catalog seeded on migration
- **WHEN** the seeding migration is applied
- **THEN** `notification_types` contains exactly `location_moved`, `ser_zone_ticket_required`, `ser_ticket_created`, and `ser_ticket_creation_failed`, each with a `label`
- **THEN** only `location_moved` and `ser_zone_ticket_required` have a `config_schema` declaring `threshold_m`; the other two have `config_schema = {}`

#### Scenario: New catalog rows backfill existing users, honoring any already-enabled auto_create_ticket
- **WHEN** the data migration for `ser_ticket_created` and `ser_ticket_creation_failed` runs
- **THEN** every existing user whose `user_preferences.auto_create_ticket` is `false` gets both new rows inserted with `enabled=false`
- **THEN** every existing user whose `user_preferences.auto_create_ticket` is `true` gets both new rows inserted with `enabled=true`, and their existing `ser_zone_ticket_required` row updated to `enabled=false`

## ADDED Requirements

### Requirement: ser_zone_ticket_required, ser_ticket_created, and ser_ticket_creation_failed are mutually exclusive with auto_create_ticket
The system SHALL treat `ser_zone_ticket_required` as togglable only while the caller's `UserPreferences.auto_create_ticket` is `false`, and `ser_ticket_created`/`ser_ticket_creation_failed` as togglable only while it is `true`. `PUT /notifications/preferences/{type_key}` SHALL reject (`422 Unprocessable Entity`, no row change) any attempt to set `enabled: true` for a type that is currently locked for the caller's `auto_create_ticket` state. Disabling a locked type (`enabled: false`) is always accepted regardless of lock state. This is enforced independently of, and in addition to, the cascading writes `PUT /preferences` performs when `auto_create_ticket` itself changes (see `user-preferences`).

#### Scenario: Enabling ser_zone_ticket_required is rejected while auto_create_ticket is true
- **WHEN** an authenticated user whose `auto_create_ticket` is `true` sends `PUT /notifications/preferences/ser_zone_ticket_required` with `enabled: true`
- **THEN** the response is `422 Unprocessable Entity` and the existing row is unchanged

#### Scenario: Enabling ser_ticket_created is rejected while auto_create_ticket is false
- **WHEN** an authenticated user whose `auto_create_ticket` is `false` sends `PUT /notifications/preferences/ser_ticket_created` with `enabled: true`
- **THEN** the response is `422 Unprocessable Entity` and the existing row is unchanged

#### Scenario: Enabling ser_ticket_creation_failed is rejected while auto_create_ticket is false
- **WHEN** an authenticated user whose `auto_create_ticket` is `false` sends `PUT /notifications/preferences/ser_ticket_creation_failed` with `enabled: true`
- **THEN** the response is `422 Unprocessable Entity` and the existing row is unchanged

#### Scenario: Disabling a locked type is always accepted
- **WHEN** an authenticated user whose `auto_create_ticket` is `true` sends `PUT /notifications/preferences/ser_zone_ticket_required` with `enabled: false`
- **THEN** the response is `200 OK`

#### Scenario: Unlocked type is unaffected
- **WHEN** an authenticated user sends `PUT /notifications/preferences/location_moved` with `enabled: true`, regardless of their `auto_create_ticket` value
- **THEN** the response is `200 OK` — `location_moved` is never locked by `auto_create_ticket`

---

### Requirement: Notifications section greys out toggles locked by auto_create_ticket
The frontend Notifications section (see `Preferences page exposes a Notifications section`) SHALL render the `ser_zone_ticket_required`, `ser_ticket_created`, and `ser_ticket_creation_failed` toggles as disabled (non-interactive) whenever their lock condition applies for the current value of `auto_create_ticket` shown on the same page, using the value already fetched via `GET /preferences` — no additional network call is introduced for this.

#### Scenario: ser_zone_ticket_required toggle is greyed out when auto-create is on
- **WHEN** the Preferences page loads with `auto_create_ticket: true`
- **THEN** the `ser_zone_ticket_required` toggle is rendered disabled

#### Scenario: ser_ticket_created and ser_ticket_creation_failed toggles are greyed out when auto-create is off
- **WHEN** the Preferences page loads with `auto_create_ticket: false`
- **THEN** the `ser_ticket_created` and `ser_ticket_creation_failed` toggles are rendered disabled

#### Scenario: Toggling auto_create_ticket in the form immediately updates the greyed-out state
- **WHEN** a user checks or unchecks the `auto_create_ticket` checkbox on the same page, before saving
- **THEN** the three toggles' disabled state updates immediately to reflect the in-progress (unsaved) value, not just the last-saved value
