## 1. Config

- [x] 1.1 Add `get_session_cleanup_retention_days() -> int` to `src/mobility_manager/config.py`, reading `SESSION_CLEANUP_RETENTION_DAYS` with int-with-fallback (default `30`), mirroring `get_vehicle_poll_interval_minutes()`'s style.
- [x] 1.2 Add `get_session_cleanup_interval_hours() -> int` to `src/mobility_manager/config.py`, reading `SESSION_CLEANUP_INTERVAL_HOURS` with int-with-fallback (default `24`), mirroring `get_ingestion_interval_hours()`'s style.
- [x] 1.3 Add `SESSION_CLEANUP_RETENTION_DAYS=30` and `SESSION_CLEANUP_INTERVAL_HOURS=24` to `.env.example` with one-line comments.

## 2. Domain

- [x] 2.1 Add `src/mobility_manager/domain/entities/session.py`: frozen dataclass `Session(id: UUID, user_id: UUID, created_at: datetime, expires_at: datetime, revoked_at: datetime | None)`.
- [x] 2.2 Add `src/mobility_manager/domain/ports/session_repository.py`: ABC `SessionRepository` with abstract methods `create(user_id: UUID, expires_at: datetime) -> Session`, `find_by_id(session_id: UUID) -> Session | None`, `revoke(session_id: UUID) -> None`, `delete_older_than(cutoff: datetime) -> int` (returns rows deleted).

## 3. Application

- [x] 3.1 Add `src/mobility_manager/application/use_cases/create_session.py`: `CreateSession` use case, depends on `SessionRepository`, `execute(user_id: UUID) -> Session` — computes `expires_at` as now + 24h and calls `session_repo.create`.
- [x] 3.2 Add `src/mobility_manager/application/use_cases/revoke_session.py`: `RevokeSession` use case, depends on `SessionRepository`, `execute(session_id: UUID) -> None` — calls `session_repo.revoke`, no-ops silently if the session doesn't exist (idempotent, matches existing logout idempotency).
- [x] 3.3 Add `src/mobility_manager/application/use_cases/validate_session.py`: `ValidateSession` use case, depends on `SessionRepository`, `execute(session_id: UUID, user_id: UUID) -> bool` — returns `True` only if the session exists, `revoked_at is None`, `expires_at` is in the future, and `session.user_id == user_id`.
- [x] 3.4 Add `src/mobility_manager/application/use_cases/cleanup_expired_sessions.py`: `CleanupExpiredSessions` use case, depends on `SessionRepository` and a retention-days value, `execute() -> int` — computes `cutoff = now - retention_days`, calls `session_repo.delete_older_than(cutoff)`, returns count deleted for logging.

## 4. Infrastructure

- [x] 4.1 Run `make db-revision` (or equivalent Alembic autogenerate) to scaffold a migration creating `sessions` table: `id UUID PRIMARY KEY`, `user_id UUID NOT NULL REFERENCES users(id)`, `created_at TIMESTAMPTZ NOT NULL`, `expires_at TIMESTAMPTZ NOT NULL`, `revoked_at TIMESTAMPTZ NULL`; add an index on `user_id`.
- [x] 4.2 Review and finalize the generated migration file under `alembic/versions/`.
- [x] 4.3 Add `src/mobility_manager/infrastructure/repositories/postgres/session_repo.py`: `PostgresSessionRepository` implementing `SessionRepository` using SQLAlchemy Core/ORM, following the existing style of `user_notification_channel_config_repo.py` or similar.
- [x] 4.4 Wire `session_repo` into `app.state` alongside `user_repo` (find the app startup/DI wiring, likely `presentation/api/main.py` or an app factory).
- [x] 4.5 Register the `CleanupExpiredSessions` use case as a scheduled job in `src/mobility_manager/infrastructure/scheduler.py`, following the existing `add_job(..., "interval", hours=...)` pattern used for parking ingestion, using `get_session_cleanup_interval_hours()`.

## 5. Presentation

- [x] 5.1 In `src/mobility_manager/presentation/api/routers/auth.py`'s `google_callback`, after `authenticate_uc.execute(...)`, call `CreateSession.execute(user_id=user.id)` (via `request.app.state`), and add `"sid": str(session.id)` to `jwt_payload`.
- [x] 5.2 In `auth.py`'s `logout`, decode the `session` cookie if present (reuse the same `jwt.decode` pattern as `deps.py`, tolerating decode failure without raising), extract `sid`, and call `RevokeSession.execute(session_id=sid)` before clearing the cookie. Must remain HTTP 204 and idempotent for missing/invalid cookies.
- [x] 5.3 In `src/mobility_manager/presentation/api/deps.py`'s `get_current_user`, after decoding the JWT and before the existing `user_id` UUID parsing, extract `sid` from the payload — raise 401 if absent. After parsing `user_id`, call `ValidateSession.execute(session_id=sid, user_id=user_id)` (via `request.app.state`) and raise 401 if it returns `False`, before proceeding to `user_repo.find_by_id`.

## 6. Tests — Domain (unit)

- [x] 6.1 `tests/domain/entities/test_session.py`: construct a `Session`, assert field equality/immutability (frozen dataclass raises on mutation attempt).
- [x] 6.2 `tests/domain/ports/test_session_repository.py` (if this repo's convention tests ABCs at all — otherwise skip; check sibling port test files for precedent). **Skipped**: no sibling `tests/domain/ports/test_*_repository.py` file exists anywhere in the repo for any of the other ABC ports (`UserRepository`, `VehicleRepository`, etc.) — this repo's convention is to exercise ports only indirectly via their use-case/repo consumers, so `SessionRepository` follows the same precedent and has no standalone ABC test.

## 7. Tests — Application (unit, mocked `SessionRepository`)

- [x] 7.1 `tests/application/use_cases/test_create_session.py`: asserts `CreateSession.execute` calls `session_repo.create` with the right `user_id` and a future `expires_at`, and returns the created `Session`.
- [x] 7.2 `tests/application/use_cases/test_revoke_session.py`: asserts `RevokeSession.execute` calls `session_repo.revoke`; asserts no exception is raised when the repo indicates the session doesn't exist.
- [x] 7.3 `tests/application/use_cases/test_validate_session.py`: table of cases — live session (True), revoked session (False), missing session (False), expired session (False), `user_id` mismatch (False).
- [x] 7.4 `tests/application/use_cases/test_cleanup_expired_sessions.py`: asserts `execute()` computes the cutoff from the configured retention days and calls `session_repo.delete_older_than` with it, returning the deleted count.

## 8. Tests — Infrastructure (integration, requires `POSTGRES_DSN`)

- [x] 8.1 `tests/infrastructure/test_session_repo_integration.py`: `create` persists a row and `find_by_id` returns it with matching fields.
- [x] 8.2 Test `revoke` sets `revoked_at` on the correct row and leaves the row present.
- [x] 8.3 Test `delete_older_than` removes rows whose `expires_at`/`revoked_at` predate the cutoff and leaves newer rows untouched.
- [x] 8.4 Test the `sessions.user_id` foreign key constraint against `users(id)`.

## 9. Tests — Presentation (E2E, `TestClient`)

- [x] 9.1 Update/extend the existing auth E2E test file (find it under `tests/presentation/`) to assert `google_callback`'s JWT payload includes a `sid` claim matching a newly created session row.
- [x] 9.2 Test: after `POST /auth/logout`, reusing the same (still non-expired) session cookie against a protected endpoint (e.g. `GET /auth/me`) returns HTTP 401.
- [x] 9.3 Test: a request with a well-formed but `sid`-less JWT (simulating a pre-change token) is rejected with HTTP 401.
- [x] 9.4 Test: `POST /auth/logout` with no cookie still returns HTTP 204.

## 10. Verification

- [x] 10.1 Run `make test` and confirm all non-integration tests pass.
- [x] 10.2 Run `make coverage` and confirm `domain/` stays at 100% and `application/` stays at or above 80%.
- [x] 10.3 Start the local stack (`docker compose up -d postgres`, run migrations, run the API), manually log in via Google, confirm a `sessions` row is created, log out, confirm `revoked_at` is set, and confirm the old cookie (if replayed) is rejected with 401. Verified manually by the maintainer against a live Google OAuth session.

## 11. Fixes from 4R review

- [x] 11.1 `src/mobility_manager/presentation/api/routers/auth.py`'s `logout`: split the single try/except into two — decode+sid-extraction keeps tolerating `(jwt.PyJWTError, ValueError)`, while `revoke_session_uc.execute(...)` gets its own `try/except Exception` (logged via `logger.exception`) so a DB error during revocation can no longer 500 and skip cookie-clearing; logout always returns 204 and clears the cookie. Added module-level `logger = logging.getLogger(__name__)`. Covered by `tests/presentation/test_auth_api.py::TestLogout::test_logout_still_returns_204_and_clears_cookie_when_revoke_raises`.
- [x] 11.2 `src/mobility_manager/config.py`'s `get_session_cleanup_retention_days()`: added a lower-bound guard — a negative parsed value now logs a warning and falls back to the default of 30, preventing `CleanupExpiredSessions` from computing a future cutoff that would delete every active session. Covered by `tests/test_config.py::TestSessionCleanupRetentionDays::test_negative_value_falls_back_to_default_and_warns`.
- [x] 11.3 Added `idx_sessions_revoked_at` and `idx_sessions_expires_at` (two separate btree indexes, not composite, so Postgres can bitmap-OR them) to `sessions_table` in `src/mobility_manager/infrastructure/orm/tables.py` and to `alembic/versions/f43a41ecb8e1_create_sessions_table.py`'s `upgrade()`/`downgrade()`, backing `CleanupExpiredSessions`/`PostgresSessionRepository.delete_older_than`'s `WHERE revoked_at < cutoff OR expires_at < cutoff` query. Local docker-compose DB re-synced and both new indexes verified present via `sqlalchemy.inspect`.
- [x] 11.4 De-duplicated the 24h session lifetime into `SESSION_LIFETIME: Final[timedelta]` in `src/mobility_manager/config.py` (not env-configurable, intentionally). `application/use_cases/create_session.py` and `presentation/api/routers/auth.py` both now import and use it instead of their own local `_SESSION_LIFETIME`/`_SESSION_MAX_AGE` constants.
- [x] 11.5 Expanded the module docstring and `get_current_user`'s docstring in `src/mobility_manager/presentation/api/deps.py` to explicitly describe the server-side `ValidateSession` revocation check (sid extraction, existence/revoked/expired/ownership check, 401 on failure) so it isn't mistaken for removable boilerplate.
- [x] 11.6 Deduplicated JWT-decode + `sid`-extraction: added `decode_session_jwt(token: str) -> dict[str, Any]` and a `_JWT_ALGORITHM` module constant to `deps.py`; `get_current_user` and `auth.py`'s `logout` both now call it instead of inlining `jwt.decode(...)`. Pure refactor — exception types raised/caught at each call site are unchanged.
