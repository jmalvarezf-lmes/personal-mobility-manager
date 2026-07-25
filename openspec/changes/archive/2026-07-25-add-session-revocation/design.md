## Context

`get_current_user` (`presentation/api/deps.py`) validates a session cookie by checking only the JWT's HS256 signature and `exp` claim. `POST /auth/logout` (`presentation/api/routers/auth.py`) only clears the cookie client-side — no server-side state changes. A token that leaks (XSS, log capture, MITM before HTTPS, shared device) stays valid for up to its full 24h lifetime regardless of logout, because there is no concept of session revocation anywhere in the system.

This design adds a server-side session store as the source of truth for "is this session still alive," while keeping the JWT signature/expiry check as a defense-in-depth first-pass filter.

## Goals / Non-Goals

**Goals:**
- Logout immediately invalidates the associated session for all future requests, even if the JWT itself hasn't expired.
- Support multiple concurrent sessions per user (multi-device) without cross-device interference.
- Keep an audit trail of session lifecycle (created, revoked) for security investigation.
- Bound the growth of the `sessions` table via a scheduled cleanup job.
- Fix the existing layering gap where `deps.py` calls a repository directly from the Presentation layer, by routing session validation through a proper use case.

**Non-Goals:**
- A user-facing "manage your active sessions" UI/endpoint (the data model supports it, but no endpoint is built here).
- Per-device selective logout (`POST /auth/logout` only knows about the calling session's own cookie).
- Replacing JWTs with pure server-side opaque tokens — the JWT is kept as the transport/signature layer; the session table adds revocability on top.

## Decisions

### 1. Sessions table (allowlist) over a token-version column
Considered a simpler alternative: one `token_version` integer column on `users`, bumped on logout, compared against a `ver` claim in the JWT. Rejected because it invalidates *all* devices on any logout and provides no audit trail — both of which matter for a security-motivated feature. The sessions table costs a new table + cleanup job but is only marginally more code, since `get_current_user` already performs one DB round-trip per request (`user_repo.find_by_id`); adding a session lookup does not introduce a new class of overhead.

### 2. `ValidateSession` use case instead of direct repo access in `deps.py`
`deps.py` currently calls `user_repo` directly from the Presentation layer, bypassing the Application layer — a pre-existing deviation from this repo's Clean Architecture rule ("Presentation: Application + FastAPI" only). Rather than propagate that shortcut to the new session check, this change introduces `ValidateSession` (application use case) that `get_current_user` calls. This is scoped strictly to the new session-validation logic; the existing `user_repo.find_by_id` call in `deps.py` is left as-is (out of scope — a pre-existing issue, not introduced by this change).

### 3. Soft revoke (`revoked_at`) instead of row deletion on logout
Deleting the row on logout is simpler but destroys the audit trail of "a logout happened here, at this time." Soft revoke preserves that for security investigation (e.g., distinguishing "session expired naturally" from "session was explicitly revoked") at the cost of needing a cleanup job — which is required either way, since sessions that merely expire (browser closed, no explicit logout) also need eventual purging.

### 4. `sid` JWT claim as the session lookup key
The JWT gains a `sid` claim (the session UUID) alongside the existing `sub` (user id) and `exp`. `ValidateSession` looks up the session by `sid`, then cross-checks `session.user_id == sub` as a consistency check. This is redundant with HMAC signature verification (which already prevents claim tampering) but is cheap and catches implementation bugs (e.g., a session row somehow associated with the wrong user).

### 5. Cleanup job follows the existing APScheduler pattern
`infrastructure/scheduler.py` already runs interval jobs (parking data ingestion) via APScheduler's `add_job(..., "interval", hours=...)`. The session cleanup job (`CleanupExpiredSessions` use case) is registered the same way, rather than introducing a new scheduling mechanism.

### 6. Retention window and cleanup interval as env-configurable
`SESSION_CLEANUP_RETENTION_DAYS` (default `30`) controls how long a revoked-or-expired row survives before cleanup purges it, matching this repo's existing `get_<name>()` / `os.environ.get(..., default)` config pattern (see `config.py`: `get_ingestion_interval_hours`, `get_vehicle_poll_interval_minutes`, etc.). A companion `SESSION_CLEANUP_INTERVAL_HOURS` (default `24`) controls how often the job runs, mirroring `INGESTION_INTERVAL_HOURS`.

## Risks / Trade-offs

- **[Risk] Deploying invalidates all existing sessions** (currently-issued JWTs lack `sid`) → Mitigation: this is an accepted one-time cost of the fix; `ValidateSession` treats a missing `sid` claim as invalid (401), forcing re-login. No migration path needed since re-authenticating via Google is a single click.
- **[Risk] Session table becomes a write/read hot path** (insert on every login, lookup on every request) → Mitigation: `user_id` and `id` (PK) are both indexed by default; row lookups by PK are O(1). No different in kind from the existing `user_repo.find_by_id` call already on this path.
- **[Risk] Cleanup job failure lets the table grow unbounded** → Mitigation: cleanup job failures are logged (matching the existing scheduler's error handling); unbounded growth is a slow-burn operational issue, not a security one — revoked/expired rows are excluded from validation regardless of whether they've been purged yet.
- **[Trade-off] Extra DB round-trip per request** (session lookup in addition to user lookup) → Accepted: could be combined into a single joined query in a future optimization, but kept as two queries here for clean separation between `ValidateSession` and the existing user-fetch logic; not a new order-of-magnitude cost.

## Migration Plan

1. Alembic migration creates the `sessions` table (additive, no data migration needed — table starts empty).
2. Deploy application code (session creation/validation/revocation + cleanup job).
3. On deploy, all existing JWTs (no `sid` claim) start failing validation — users are redirected to re-login on their next request. No coordinated rollout needed; this happens naturally per-request.
4. Rollback: revert application code; the `sessions` table can remain (unused) or be dropped in a follow-up migration — its presence is harmless to the pre-change code path.

## Open Questions

None outstanding — retention window, cleanup interval, revoke strategy, and layering approach were resolved during exploration.
