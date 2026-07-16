## 1. Database & Migrations

- [x] 1.1 Add Alembic revision creating `notification_types` (`key TEXT PRIMARY KEY`, `label TEXT NOT NULL`, `config_schema JSONB NOT NULL`), seeded with `location_moved` and `ser_zone_ticket_required`, both `config_schema = {"threshold_m": {"type": "integer", "min": 1}}`
- [x] 1.2 Add Alembic revision creating `user_notification_preferences` (`user_id UUID REFERENCES users(id)`, `type_key TEXT REFERENCES notification_types(key)`, `enabled BOOLEAN NOT NULL`, `config JSONB NOT NULL DEFAULT '{}'`, `updated_at TIMESTAMPTZ NOT NULL`, composite PK `(user_id, type_key)`)
- [x] 1.3 Add data migration backfilling `enabled=false, config={}` rows for every existing `users` row × every `notification_types` row (`INSERT ... SELECT ... ON CONFLICT DO NOTHING`) — opt-in, not opt-out: this intentionally stops both notification kinds for every existing user until they re-enable them
- [x] 1.4 Add both new tables to `src/mobility_manager/infrastructure/orm/tables.py`

## 2. Domain & Repository Layer

- [x] 2.1 Add `NotificationType` and `UserNotificationPreference` domain entities (frozen dataclasses) under `src/mobility_manager/domain/entities/`
- [x] 2.2 Add `NotificationPreferencesRepository` port under `src/mobility_manager/domain/ports/` with `list_types`, `ensure_defaults`, `find_by_user_id`, `update`
- [x] 2.3 Implement `NotificationPreferencesRepository` for Postgres under `src/mobility_manager/infrastructure/repositories/postgres/`
- [x] 2.4 Add config-schema validation helper (validates a `config` dict against a type's `config_schema`, e.g. `threshold_m` is a positive integer) for reuse by both the API layer and any future type

## 3. Config

- [x] 3.1 Rename `get_notification_movement_threshold_meters()` to `get_default_notification_movement_threshold_meters()` in `src/mobility_manager/config.py`, reading `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` (fallback `"50"`)
- [x] 3.2 Update `.env.example`: rename `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` to `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`

## 4. Notification Handlers

- [x] 4.1 Update `NotificationDispatchHandler` (`notification_dispatch_handler.py`) to accept `NotificationPreferencesRepository`, check the owner's `location_moved` preference first (skip immediately if missing/disabled, before `VehicleLocationRepository.get_previous`), and resolve the effective threshold from `config.threshold_m` falling back to `get_default_notification_movement_threshold_meters()`
- [x] 4.2 Update `SerTicketTriggerHandler` (`ser_ticket_trigger_handler.py`) to accept `NotificationPreferencesRepository`, check the owner's `ser_zone_ticket_required` preference first (skip immediately if missing/disabled, before any previous-location or zone lookup), and resolve its own effective threshold independently from `location_moved`'s
- [x] 4.3 Update both handlers' module/method docstrings to reflect the new preference-gated behavior (remove references to unconditional sending)

## 5. API

- [x] 5.1 Add `GET /notifications/types` (session-protected) returning the full `notification_types` catalog
- [x] 5.2 Add `GET /notifications/preferences` (session-protected) returning the current user's preferences merged with catalog defaults (missing `config` keys resolved via the fallback default)
- [x] 5.3 Add `PUT /notifications/preferences/{type_key}` (session-protected) accepting `{enabled, config}`, validating `type_key` exists (`404` if not) and `config` against its schema (`422` if invalid), persisting via `NotificationPreferencesRepository.update`
- [x] 5.4 Add Pydantic request/response models for the above under `presentation/api/routers/` (new `notification_preferences.py` router or similar)

## 6. Wiring

- [x] 6.1 Construct the Postgres `NotificationPreferencesRepository` and inject it into `NotificationDispatchHandler` and `SerTicketTriggerHandler` in `app.py`'s lifespan
- [x] 6.2 Register the new router in `app.py`
- [x] 6.3 Call `NotificationPreferencesRepository.ensure_defaults(user_id)` in the Google login flow (`authenticate_google_user`), alongside the existing `UserPreferencesRepository.ensure_default` call — inserted rows are `enabled=false, config={}`, so new users also start opted out of every type

## 7. Frontend

- [x] 7.1 Add API client calls for `GET /notifications/types`, `GET /notifications/preferences`, `PUT /notifications/preferences/{type_key}`
- [x] 7.2 Add a "Notifications" section to the Preferences page: one toggle per type from the catalog, reflecting current preference state
- [x] 7.3 Render an inline config control (numeric input for `threshold_m`) when a type is enabled and its `config_schema` declares that field; hide it when disabled
- [x] 7.4 Wire toggle/config changes to `PUT /notifications/preferences/{type_key}` and reflect the saved response
- [x] 7.5 Add/update i18n strings for the new section (EN/ES)

## 8. Tests

- [x] 8.1 Unit tests for `NotificationPreferencesRepository` (Postgres impl): `ensure_defaults` backfill behavior, `update` scoping to one `(user_id, type_key)`
- [x] 8.2 Unit tests for `NotificationDispatchHandler`: disabled preference skips before location lookup, per-user threshold override, fallback to env-var default
- [x] 8.3 Unit tests for `SerTicketTriggerHandler`: disabled preference skips before location/zone lookup, independent threshold from `location_moved`
- [x] 8.4 API tests for `GET /notifications/types`, `GET /notifications/preferences`, `PUT /notifications/preferences/{type_key}` (happy path, 401, 404, 422)
- [x] 8.5 Migration test/verification: backfill produces exactly one row per existing user per catalog type, `enabled=false, config={}`; re-running the migration is idempotent

## 9. Deployment

- [x] 9.1 Update deployment configuration/secrets to rename `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` to `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`
- [x] 9.2 Confirm migrations run before the new handler code deploys (backfill must precede the first request that reads `user_notification_preferences`)
