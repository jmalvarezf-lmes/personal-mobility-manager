## Context

Today, `NotificationDispatchHandler` (vehicle-moved) and `SerTicketTriggerHandler` (SER-zone-ticket-required) both subscribe to the single domain event `VehicleLocationUpdated` and both send unconditionally to any user with a `preferred_notification_channel` connected. Their only tunable behavior is a shared `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` env var, read independently by each handler as a movement-debounce gate — `SerTicketTriggerHandler` deliberately reuses `NotificationDispatchHandler`'s threshold logic (see its module docstring) even though the two notifications are semantically distinct ("did the vehicle move enough to be worth telling the owner where it is" vs. "did the vehicle move enough to be worth re-checking whether it's now somewhere requiring a SER ticket"). Both handlers' existing specs contain the identical sentence: "This capability does not implement per-event-type opt-in/opt-out" — this change fulfills that.

`UserPreferences` already exists as a 1:1 per-user row (`user_preferences` table) with a self-healing `ensure_default` pattern invoked at login. Per-notification-type preferences are a 1:many relationship (one row per `(user, type)`), so they get their own table rather than extending `user_preferences`.

## Goals / Non-Goals

**Goals:**
- Let each user independently enable/disable `location_moved` and `ser_zone_ticket_required` notifications.
- Let each user independently configure `threshold_m` for each type (no longer shared).
- Represent the set of notification types as DB-backed, queryable catalog data (`notification_types`) so the frontend can render a settings UI generically, and so a future type can be added via a migration + a small config sub-form rather than a bespoke settings screen each time.
- Default every user — existing and new — to `enabled=false` for every notification type: nobody has ever explicitly consented to either notification kind today (they were unconditional, not opted-into), so this migration must not be read as auto-enrolling anyone. Users start receiving a type only after they explicitly turn it on in Preferences.
- Keep `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` as a live, restart-only-tunable fallback default — not baked into stored preference rows — so ops can change the systemwide default `threshold_m` without a data migration, ready for whenever a user does opt in.

**Non-Goals:**
- Adding a third notification type. The catalog becomes extensible, but wiring a new domain event/handler is still a code change; this proposal only covers `location_moved` and `ser_zone_ticket_required`.
- An admin UI for managing `notification_types` rows. They're migration-seeded.
- Per-type notification language or channel overrides — those stay on `UserPreferences` (`notification_language`, `preferred_notification_channel`) and continue to apply uniformly underneath the per-type enable/config layer.
- Generalizing `config_schema` defaults into a DB-seeded `default_config` column. Deferred intentionally (see Decisions) until a second config field shape actually needs it.

## Decisions

**1. Two new tables (`notification_types`, `user_notification_preferences`) instead of a code-only registry or more `user_preferences` columns.**
A code-only registry can't be queried by `GET /notifications/types`, and fixed columns on `user_preferences` don't fit a 1:many, growing set of types. A DB catalog table lets the type list grow via migration without necessarily touching API code.
`notification_types(key TEXT PRIMARY KEY, label TEXT NOT NULL, config_schema JSONB NOT NULL)`, seeded with `location_moved` and `ser_zone_ticket_required`, both with `config_schema = {"threshold_m": {"type": "integer", "min": 1}}`.
`user_notification_preferences(user_id UUID REFERENCES users(id), type_key TEXT REFERENCES notification_types(key), enabled BOOLEAN NOT NULL, config JSONB NOT NULL DEFAULT '{}', updated_at TIMESTAMPTZ NOT NULL, PRIMARY KEY (user_id, type_key))`.

**2. Independent `threshold_m` per type, not shared.**
`SerTicketTriggerHandler` reused `NotificationDispatchHandler`'s threshold as a debounce, but the two are semantically different checks. Each type's `config` is its own independent JSON blob; a user can set `location_moved.threshold_m = 20` and `ser_zone_ticket_required.threshold_m = 200` without one affecting the other. Both default to the same env var value until a user overrides one.

**3. Every inserted row starts `enabled=false, config={}` — both the migration backfill and login-time `ensure_defaults`.**
`config` is never snapshotted with a numeric default (see below), and `enabled` is never defaulted to `true`: this is an opt-in model, not opt-out. Neither existing users (via migration backfill) nor new users (via login-time `ensure_defaults`) have ever explicitly asked for either notification kind — the prior "unconditional for everyone" behavior was never a considered choice, so this change does not carry it forward as an implicit default. A user only starts receiving a type after an explicit `PUT /notifications/preferences/{type_key}` with `enabled: true`.
Leaving `config={}` still matters even though `enabled=false`: once a user does enable a type without also setting `threshold_m`, they should get the current systemwide default rather than a stale value frozen at backfill time. At read time, handlers resolve `config.get("threshold_m", get_default_notification_movement_threshold_meters())`. This makes the env var a true "fallback, not a stored default": changing it changes behavior instantly for every user who hasn't explicitly customized that type.

**4. Disabled types skip before any lookup, not just before the send.**
Both handlers currently do previous-location lookup → distance check → (for SER) zone lookup → send. The preference check (`enabled`) now happens first, immediately after the vehicle lookup, and returns before touching `VehicleLocationRepository.get_previous` or the zone/ticket use cases at all. This separates "does the user want this notification kind" (preference, cheap) from "is this occurrence worth notifying about" (threshold debounce, the existing logic), rather than nesting the former inside the latter.

**5. REST shape: `GET /notifications/types`, `GET /notifications/preferences`, `PUT /notifications/preferences/{type_key}`.**
Per-type `PUT` (not a bulk array `PUT /notifications/preferences`) so toggling one switch sends one small request and a client that only knows about today's two types can never accidentally clobber a third type it doesn't render. Both `GET`s are session-protected (`401` anonymous), consistent with the existing `/preferences` endpoints — `notification_types` isn't user-specific data, but there's no current use case for exposing it pre-login, so it stays behind auth for consistency until one appears.
`PUT` body: `{"enabled": bool, "config": {...}}`. Validates `config` against the type's `config_schema`; `404` if `type_key` isn't in the catalog, `422` if `config` fails schema validation, `401` if anonymous.

**6. `type_key` values (`location_moved`, `ser_zone_ticket_required`) are decoupled from `notification_templates.py`'s existing `render()` keys (`vehicle_moved`, `ser_ticket_required`).**
They describe the same notifications but aren't required to be the same string — each handler maps its own `type_key` to its own `render()` key explicitly in code. Renaming the template keys to match wasn't judged worth the churn for this change; see Open Questions.

**7. Login-time backfill follows the existing `ensure_default` pattern, generalized.**
`UserPreferencesRepository.ensure_default(user_id)` already runs at Google login (`authenticate_google_user`) and is idempotent/self-healing. A new `NotificationPreferencesRepository.ensure_defaults(user_id)` runs alongside it, looping `notification_types` and inserting any `(user_id, type_key)` row not already present (`enabled=false, config={}`), so a user created before a new type existed self-heals on next login exactly like `user_preferences` does today — and so every user, brand-new or pre-existing, always has a row per type, just disabled until they opt in.

**8. New port/repository, not an extension of `UserPreferencesRepository`.**
`NotificationPreferencesRepository` (port) + Postgres implementation, injected into both event handlers alongside their existing dependencies. Kept separate because the shape (list of rows per user, catalog-joined) and its consumers (event handlers, not the preferences page's four scalar fields) are distinct from `UserPreferencesRepository`.

## Risks / Trade-offs

- **[Risk]** Every existing user stops receiving both notification kinds immediately on deploy, since backfilled rows are `enabled=false` — this is a real, user-visible behavior change, not a no-op migration. → **Mitigation**: this is an intentional product decision (explicit opt-in, since no consent was ever captured for the prior unconditional behavior), not an oversight to be masked. Consider whether an out-of-band signal (e.g. an in-app banner pointing to the new Preferences section) is warranted so users know to opt back in; that communication is outside this change's technical scope but worth flagging to product before this ships.
- **[Risk]** Splitting the threshold per type changes SER-zone debounce cadence away from location's the moment a user enables and customizes either one. → **Mitigation**: `config` defaults to `{}` (env-var fallback), so a user who enables a type without setting `threshold_m` gets the current systemwide default rather than a stale or arbitrary value.
- **[Risk]** A `notification_types` row can exist without a subscribed handler behind it (e.g. seeded ahead of the handler code landing), silently accepting preferences that do nothing. → **Mitigation**: this is a docs/process concern, not a runtime failure — an unmatched `type_key` only affects preference storage, never raises. Call out in `tasks.md` that the catalog row and the handler wiring land in the same change.
- **[Risk]** `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` → `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS` is a breaking env var rename; an un-updated deployment silently reverts to the `50` default instead of an operator's previously-configured value. → **Mitigation**: called out as **BREAKING** in the proposal; `tasks.md` includes updating `.env.example` and deployment configuration.
- **[Risk]** Backfill migration inserts two rows per existing user in one pass. → **Mitigation**: this project's user count is small (personal-project scale, no existing batching precedent in other migrations); a single `INSERT ... SELECT` is sufficient.

## Migration Plan

1. Alembic revision: create `notification_types`, seed `location_moved` and `ser_zone_ticket_required` with their `config_schema`.
2. Alembic revision: create `user_notification_preferences` (FKs to `users` and `notification_types`, composite PK).
3. Data migration (same or follow-up revision): `INSERT INTO user_notification_preferences (user_id, type_key, enabled, config, updated_at) SELECT id, key, false, '{}', now() FROM users CROSS JOIN notification_types ON CONFLICT DO NOTHING`.
4. Deploy backend: `config.py` rename, new port + Postgres repo, updated handlers, new router, `app.py` wiring, `NotificationPreferencesRepository.ensure_defaults` added to the login flow.
5. Rename env var in deployment configuration (`.env.example`, CI/deploy secrets) from `NOTIFICATION_MOVEMENT_THRESHOLD_METERS` to `DEFAULT_NOTIFICATION_MOVEMENT_THRESHOLD_METERS`.
6. Deploy frontend: new "Notifications" section on the Preferences page.

**Rollback**: revert handler code to the previous unconditional/shared-env-var behavior; the new tables can remain unused (no destructive down-migration required) or be dropped via a down-revision if desired; revert the env var rename.

## Open Questions

- Should `notification_types` eventually carry a DB-seeded `default_config` column, decoupling each type's default from the single shared env var? Explicitly deferred — current design keeps one env-var fallback for both types until a real need for divergence appears.
- Should `type_key` be unified with `notification_templates.py`'s `render()` keys instead of staying decoupled? Left as a future cleanup, not blocking this change.
- Should `GET /notifications/types` become unauthenticated later (e.g. to render a "what notifications exist" marketing/onboarding view before login)? Not needed now; stays session-protected.
