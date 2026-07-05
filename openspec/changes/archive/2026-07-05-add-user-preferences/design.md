## Context

Ticket creation (a near-term follow-up change) needs two per-user settings: a default ticket duration and an auto-create-vs-notify toggle. There is no existing place to store per-user settings. The codebase already has a precedent for a 1:1 "config" table keyed by an owning entity's primary key (`vehicle_configs`, keyed by `vehicle_id`), but that table's repository raises `VehicleConfigNotFoundError` when a row is missing, because vehicle configs are only ever created going forward at vehicle-registration time.

Users are different: all current users already exist (provisioned via Google OAuth upsert in `authenticate_google_user.py` / `PostgresUserRepository.upsert`), so a new `user_preferences` table would start out with zero rows for existing accounts. The chosen approach avoids a one-off backfill migration by piggybacking preferences-row creation onto the same upsert-on-login path that already exists for `users`.

## Goals / Non-Goals

**Goals:**
- Every user has a `user_preferences` row by the time they can reach the preferences page, with no "row not found" branch needed by readers (including the future ticket-creation use case).
- Existing users get a preferences row automatically, the next time they log in — no manual backfill migration required.
- Preferences are structured, typed columns (not a JSON blob), consistent with the rest of the schema's style.
- Preferences are only visible/editable when logged in.

**Non-Goals:**
- Ticket creation itself (a separate, later change) — this change only prepares the settings it will read.
- A generic/extensible preferences framework (e.g. key-value or JSONB) — out of scope; revisit if the number of preferences grows significantly.
- Any preference beyond the two named here (`default_ticket_duration_minutes`, `auto_create_ticket`).

## Decisions

### 1. Typed columns table, not JSONB/key-value
`user_preferences` gets one column per preference (`default_ticket_duration_minutes INT NOT NULL DEFAULT 60`, `auto_create_ticket BOOLEAN NOT NULL DEFAULT false`), mirroring `vehicle_configs`. Rationale: the set of preferences is small and expected to stay small; typed columns get DB-level constraints and keep the repo/entity mapping trivial, consistent with the project's existing convention of a migration per schema change.

### 2. Row provisioned via the login upsert, not lazily or via backfill migration
Extend `authenticate_google_user.py` (and `PostgresUserRepository`, or a new sibling repository invoked alongside it) so every login upserts a `user_preferences` row with default values if none exists yet, using `INSERT ... ON CONFLICT (user_id) DO NOTHING` (unlike the `users` upsert, preference values themselves are never overwritten by login — only their existence is guaranteed).

The `users` upsert and the preferences `ensure_default` call are two independently atomic operations, each in its own transaction — not one shared database transaction. This is intentional: both writes are individually safe (the `users` upsert is a standard upsert; `ensure_default` is `ON CONFLICT DO NOTHING`, so it never corrupts existing data), and `ensure_default` is idempotent, so if a process crash or connection drop happens between the two commits, the affected user is simply missing their preferences row until their next login, at which point it's created — no partial or inconsistent state ever persists beyond that narrow, self-healing window.

Alternatives considered:
- **Lazy defaults-in-code on GET, write on first PUT**: rejected because it forces every future reader (ticket creation included) to handle "no row yet" by falling back to in-code defaults, duplicating the default values in two places (DB column default and application code) and risking drift.
- **One-off data migration backfilling existing users**: rejected because it doesn't help *new* signups either (they'd still need row creation somewhere), so the login-upsert hook is needed regardless — making a separate backfill migration redundant.

### 3. Auto-create-ticket defaults to `false`
`auto_create_ticket` defaults to `false` (notify-only). Rationale: auto-creating a ticket is a real-money action; requiring explicit opt-in is the safer default.

### 4. API shape: single GET/PUT resource, not per-field endpoints
`GET /preferences` returns the current user's full preferences object; `PUT /preferences` replaces both fields at once (full-resource PUT, not PATCH), consistent with `vehicles` update endpoints in this codebase. Both routes require an authenticated session (same auth dependency used by `/vehicles`).

### 5. Nav becomes a dropdown menu under the user's email
`Nav.tsx` currently renders flat links (`My Vehicles`, email, `Logout`) when logged in. This change replaces that block with a single dropdown trigger (the user's email) that expands to `My Vehicles`, `Preferences`, `Logout`. The language selector and `Map` link remain outside the dropdown, since they aren't account-scoped.

## Risks / Trade-offs

- **[Risk] Login upsert now does two writes (users + user_preferences) instead of one, in two separate transactions.** → Mitigation: both writes are individually atomic and idempotent (see Decision 2); a failure between them leaves the user without a preferences row only until their next login, which self-heals it. Accepted trade-off rather than introducing a shared-transaction/unit-of-work mechanism for a narrow, self-healing edge case.
- **[Risk] `ON CONFLICT DO NOTHING` on `user_preferences` means an existing row is never touched by login, even if a future default changes.** → Mitigation: acceptable — column defaults only affect newly inserted rows, matching normal migration semantics; changing a default for existing users is a deliberate, separate data migration if ever needed.
- **[Trade-off] Full-resource PUT means the frontend must always send both fields, even if only one changed.** → Acceptable given there are only two fields today; revisit if the preferences set grows.

## Migration Plan

1. Add Alembic migration creating `user_preferences` (`user_id UUID PK/FK -> users.id`, `default_ticket_duration_minutes INT NOT NULL DEFAULT 60`, `auto_create_ticket BOOLEAN NOT NULL DEFAULT false`, `updated_at TIMESTAMPTZ NOT NULL`).
2. Deploy backend changes (repository, use case update, router) — existing users get their row lazily upserted on next login; no explicit backfill step needed.
3. Deploy frontend changes (Preferences page, nav dropdown).
4. Rollback: standard Alembic downgrade drops the table; revert the upsert-hook code change; no data loss beyond preference values themselves (all derivable defaults).

## Open Questions

None outstanding — duration default (60 minutes) and auto-create default (`false`) are confirmed.
