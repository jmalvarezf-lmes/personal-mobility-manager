## Why

Ticket creation (upcoming) needs two per-user settings before it can be built: how long a SER ticket should last by default, and whether to create it automatically or just notify the user their vehicle is parked in a SER zone. There is currently no place to store or edit per-user settings, so this change adds that foundation ahead of the ticket-creation work.

## What Changes

- Add a `user_preferences` table (1:1 with `users`), storing `default_ticket_duration_minutes` (int, default 60) and `auto_create_ticket` (bool, default false).
- Extend the Google login upsert flow (`authenticate_google_user` / `PostgresUserRepository`) to also upsert a `user_preferences` row with defaults whenever a user logs in, so every user — new or existing — has a preferences row without a separate backfill migration.
- Add a protected `GET /preferences` and `PUT /preferences` API for reading and updating the current user's preferences.
- Add a frontend "Preferences" page (protected route) with a form for the two settings.
- Replace the current flat nav links (My Vehicles, email, Logout) with a dropdown menu under the user's email, containing My Vehicles, Preferences, and Logout.

## Capabilities

### New Capabilities
- `user-preferences`: Storage, API, and UI for per-user settings (default ticket duration, auto-create-ticket toggle), created automatically on login.

### Modified Capabilities
- `user-identity`: Login upsert now also provisions a default `user_preferences` row for the user.

## Impact

- **Database**: new `user_preferences` table + migration.
- **Backend**: `domain/entities/user_preferences.py`, `domain/ports/user_preferences_repository.py`, `infrastructure/repositories/postgres/user_preferences_repo.py`, new `presentation/api/routers/preferences.py`, changes to `authenticate_google_user.py` use case.
- **Frontend**: new `PreferencesPage.tsx`, new route in `App.tsx`, `Nav.tsx` reworked to a dropdown menu, new `api/preferences.ts` client.
- No breaking changes; purely additive except for the `Nav.tsx` visual restructuring.
