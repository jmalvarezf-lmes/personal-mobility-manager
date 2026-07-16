## Why

Vehicle-moved and SER-zone-ticket-required notifications are currently unconditional for every user (any user with a connected channel receives both kinds) and share a single global `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` env var as their only tunable behavior. Users cannot opt out of one notification kind while keeping the other, cannot tune sensitivity per kind, and adding a new notification kind in the future has no consistent place to expose its own settings. This change moves that control to per-user, per-notification-type preferences.

## What Changes

- Add a `notification_types` catalog table (seeded via migration) listing the platform's notification kinds — `location_moved` and `ser_zone_ticket_required` — each with a label and a `config_schema` describing its configurable fields (e.g. `threshold_m`).
- Add a `user_notification_preferences` table: one row per `(user_id, type_key)` with `enabled` (bool) and `config` (jsonb), foreign-keyed to `notification_types`.
- Add REST endpoints: `GET /notifications/types` (catalog), `GET /notifications/preferences` (current user's rows merged with catalog defaults for any type not yet customized), `PUT /notifications/preferences/{type_key}` (update one type's `enabled`/`config`).
- Update `NotificationDispatchHandler` and `SerTicketTriggerHandler` to look up the owner's `(user_id, type_key)` preference first and return immediately if disabled, before any previous-location or zone lookups — replacing the current always-on behavior.
- Replace `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` with `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`: no longer read directly by the handlers, it becomes the fallback `threshold_m` value used (a) to backfill existing users' preference rows during migration and (b) at runtime whenever a user has no override for that field. **BREAKING**: deployments must rename this env var; until renamed, the new default falls back to `50`, same as today.
- Migration backfills every existing user with `enabled=false` rows for both types, and new users likewise get `enabled=false` rows created at login for every catalog type. This is a deliberate opt-in model: no user has ever explicitly consented to either notification kind, so nobody receives them until they turn each one on in Preferences. **BREAKING**: existing users will stop receiving vehicle-moved and SER-zone-ticket notifications immediately on deploy, until they opt back in.
- Add a "Notifications" section to the frontend Preferences page: a toggle per type sourced from `GET /notifications/types` + `GET /notifications/preferences`, with an inline `threshold_m` input shown when a type is enabled and its schema declares that field.

## Capabilities

### New Capabilities
- `notification-type-preferences`: catalog of notification types plus per-user enable/disable and config (e.g. movement threshold) for each, exposed via `/notifications/types` and `/notifications/preferences`, including the frontend settings UI.

### Modified Capabilities
- `vehicle-location-notification`: `NotificationDispatchHandler` no longer sends unconditionally to every user with a channel connected — it now checks the user's `location_moved` preference (enabled + `threshold_m`) before proceeding, sourced from `user_notification_preferences` instead of the global `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` env var.
- `ser-zone-ticket-notification`: `SerTicketTriggerHandler` no longer sends unconditionally — it now checks the user's `ser_zone_ticket_required` preference (enabled + `threshold_m`) first and skips immediately (before the previous-location/zone lookups) when disabled, sourced from `user_notification_preferences` instead of the shared global threshold env var.

## Impact

- New Alembic migrations: `notification_types` table (seeded with `location_moved`, `ser_zone_ticket_required`), `user_notification_preferences` table, and a backfill of existing users.
- `src/mobility_manager/config.py`: `get_notification_movement_threshold_meters()` renamed to `get_default_notification_movement_threshold_meters()`, reading `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`.
- `src/mobility_manager/application/event_handlers/notification_dispatch_handler.py` and `ser_ticket_trigger_handler.py`: gated by per-user preference lookup instead of unconditional send + shared env var.
- New domain entity, repository port, and Postgres repository implementation for notification types and user notification preferences.
- New FastAPI router (`presentation/api/routers/notification_preferences.py` or similar) and wiring in `app.py`'s lifespan.
- Frontend: Preferences page gains a new section; API client gains calls to the new endpoints.
- `.env.example`: `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` renamed to `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`.
