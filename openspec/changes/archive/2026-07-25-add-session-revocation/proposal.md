## Why

Logout only clears the browser cookie — the JWT itself stays valid (signature + expiry check only) for up to 24h after the user "logs out." A stolen or leaked token keeps working after logout, giving an attacker a full-length session window regardless of the victim's action.

## What Changes

- Add a `sessions` table tracking one row per login: `id`, `user_id`, `created_at`, `expires_at`, `revoked_at`.
- Login (`/auth/google/callback`) creates a session row and embeds its `id` as a `sid` claim in the JWT. **BREAKING**: JWT payload shape changes.
- Logout (`/auth/logout`) soft-revokes the session (`revoked_at = now()`) in addition to clearing the cookie.
- `get_current_user` validates the session server-side (not revoked, not expired, `user_id` matches `sub`) in addition to the existing JWT signature/expiry check, via a new `ValidateSession` use case.
- A scheduled cleanup job purges revoked/expired session rows older than a configurable retention window (default 30 days, env var).
- **BREAKING**: Deploying this change invalidates all currently-issued JWTs (they lack a `sid` claim) — every logged-in user is forced to re-authenticate once.

## Capabilities

### New Capabilities
- `session-management`: Server-side session lifecycle — the `sessions` table, session creation/revocation/lookup, and the scheduled cleanup job that purges old rows after the retention window.

### Modified Capabilities
- `google-auth`: Callback now creates a session and embeds `sid` in the JWT; logout now revokes the session server-side, not just the cookie; JWT validation (`get_current_user`) now requires a live, non-revoked session in addition to a valid signature/expiry.

## Impact

- **Domain**: new `Session` entity, new `SessionRepository` port.
- **Application**: new use cases `CreateSession`, `RevokeSession`, `ValidateSession`, `CleanupExpiredSessions`.
- **Infrastructure**: new `PostgresSessionRepository`, new Alembic migration for `sessions` table, new scheduler job (same pattern as the existing parking-ingestion scheduler), new `SESSION_CLEANUP_RETENTION_DAYS` config var.
- **Presentation**: `auth.py` (`google_callback`, `logout`) and `deps.py` (`get_current_user`) updated to use the session lifecycle use cases.
- **Existing sessions**: all currently-issued JWTs become invalid on deploy (missing `sid` claim) — forces a one-time global re-login.
