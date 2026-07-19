## Context

FastAPI + Pydantic v2 backend, hexagonal layout (`presentation/api/routers` → `application/use_cases` → `infrastructure/repositories`). All request bodies already use Pydantic models, but:

- No schema uses `model_config = ConfigDict(extra="forbid")` — Pydantic v2's default (`extra="ignore"`) applies everywhere, so unknown fields are silently dropped rather than rejected.
- `slowapi` is installed and wired globally (`app.state.limiter`, `SlowAPIMiddleware`) but only `POST /parking/ser-zone` and `POST /vehicles/{token}/location` carry `@limiter.limit(...)`. No auth or credential-submission endpoint is throttled.
- Ownership checks (`vehicle.user_id != current_user.id` → 403) are duplicated inline across 5+ routes in `routers/vehicles.py`.
- `validate_notification_config()` (`domain/value_objects/notification_config_schema.py`) explicitly ignores `config` keys not declared in the type's `config_schema`, by documented design ("forward-compatible with a schema key this validator doesn't understand yet").

This is a real-users-on-the-internet deployment (confirmed with the project owner), so credential-bearing endpoints (Toyota register/update, ElParking connect) and the OAuth callback are treated as higher priority than cosmetic tightening elsewhere.

## Goals / Non-Goals

**Goals:**
- Reject unknown top-level request fields everywhere, by default, without relying on each schema author remembering to opt in.
- Apply real format validation where a real format exists (VIN, Toyota locale); apply defensive `max_length` bounds everywhere else that currently has none.
- Extend rate limiting to endpoints that accept credentials or drive an auth flow.
- Remove the duplicated ownership-check pattern without changing its observable behavior.
- Make notification `config` strict about unknown keys, matching the `extra="forbid"` posture applied to typed request bodies.

**Non-Goals:**
- Pagination on unbounded list endpoints (`/cities`, `/parking/ser-zones`) — flagged during exploration but out of scope for this change; it's a response-shape/performance concern, not input validation.
- CORS `allow_headers` tightening, HSTS header, distributed (Redis-backed) rate-limit storage — separate hardening concerns, not request-validation.
- Changing how Telegram webhook payloads are parsed (`await request.json()` with shared-secret auth) — different trust model (external webhook, not a typed user-facing endpoint); worth a follow-up, not bundled here.
- Verifying that a submitted VIN/credential actually belongs to a real account — format validation only, no calls to Toyota's API to confirm authenticity.

## Decisions

**1. `extra="forbid"` via a shared base class, not per-model `model_config`.**
Add one `StrictRequestModel(BaseModel)` with `model_config = ConfigDict(extra="forbid")` in `schemas.py`, and have every request-body model inherit from it instead of `BaseModel` directly (response models stay on plain `BaseModel` — being lenient about what we return is fine; being lenient about what we accept is not). Rejected alternative: adding `model_config` individually to each of the ~12 request models — works, but a newly added schema that forgets it silently reverts to the current permissive behavior. A shared base makes forgetting impossible rather than merely unlikely.

**2. VIN and Toyota-locale validation live as Pydantic `field_validator`s on `RegisterToyotaRequest`/`UpdateToyotaRequest`, not in the use case layer.**
Both are pure syntactic checks with no I/O (locale check calls `pytoyoda.utils.locale.is_valid_locale()`, a pure function; VIN is a regex), so they belong at the API boundary and should produce `422`, not a use-case-level domain exception. This matches the existing pattern for `lat`/`lon` bounds (`Field(ge=..., le=...)`) and keeps the use case layer free of transport-format concerns, consistent with the existing hexagonal split.

**3. Defensive `max_length` values chosen conservatively, not derived from a spec:**
`username`/`locale` (Toyota) → 100; `password` (Toyota) → 200 (headroom over the 100 already used for ElParking's password, since Toyota's actual limit is unknown); `display_name` → 100 (matches typical UI-nickname conventions elsewhere in the schema, e.g. no existing field goes higher); `city_code` → 50 (generously above the one seeded value, `"madrid"`, since `cities.code` is `TEXT` with no DB-level cap — this is a request-hygiene bound only, not a DB-mirroring one like `zone_number`'s `max_length=10`, which does mirror a real `VARCHAR(10)` column). These are sanity bounds against abuse (e.g. multi-MB strings), not business rules — if a real constraint surfaces later (e.g. Toyota's actual username format), it supersedes these.

**4. `provider` and `channel` path params validated against the same live registries their sibling endpoints already use, not hardcoded `Literal`s.**
`GET /ser-ticket-providers/connections` and `GET /notifications/available-channels` already source their "known" sets dynamically (`ConnectSerTicketProviderRequest`'s discriminated union for providers; `app.state.notification_channels.keys()` for channels). The `DELETE` path params for both should validate against those same sources — a FastAPI dependency that 404s on an unknown value — rather than a hardcoded `Literal["elparking"]` that would need a code change every time a provider/channel is added, unlike the `Literal` used for `sort` (`asc`/`desc`), which really is fixed forever. `type_key` needs no change: `update_notification_preference` already 404s on an unknown key before doing anything else.

**5. Ownership check is a shared FastAPI dependency for no-body routes, and a shared plain function called manually for body-bearing routes — not a single `Depends()` used everywhere.**

**Amended after the post-implementation 4R review** (both `review-risk` and `review-reliability` independently caught the same issue): FastAPI resolves *all* `Depends(...)` parameters — including sub-dependencies — before it parses or validates the request body (confirmed by tracing `fastapi/dependencies/utils.py`: the sub-dependant resolution loop runs before `request_body_to_args()`). A single `Depends(require_owned_vehicle)` used on a route that also takes a body therefore lets the 404/403 ownership check short-circuit *before* the body is ever validated — silently reordering behavior relative to the original inline check (which ran after FastAPI had already bound/validated the body, since the route handler only starts executing once every parameter, including the body, has resolved). That reordering lets a non-owner learn "this vehicle exists and isn't yours" using an empty or malformed body, where before they needed a body that passed full validation first — same information, but zero-effort to obtain instead of requiring a crafted valid payload.

The fix keeps both call shapes on one shared 404/403 implementation instead of choosing one at the expense of the other:
- `require_owned_vehicle(vehicle_id, request, current_user=Depends(get_current_user)) -> Vehicle` — the `Depends()`-based version — is used on the four routes with **no request body** (`GET /vehicles/{id}`, `DELETE /vehicles/{id}`, `GET /vehicles/{id}/location`, `DELETE /vehicles/{id}/ser-parking-exemptions`), where dependency-vs-body ordering is moot.
- `get_owned_vehicle_or_raise(request, vehicle_id, current_user) -> Vehicle` — a plain function, not a `Depends()` target — is called as the first line inside the two route handlers that **do** take a body (`PUT /vehicles/{id}`, `POST /vehicles/{id}/ser-parking-exemptions`), *after* `body: ...Request` is already a resolved parameter, restoring the original body-then-ownership order exactly. Both functions delegate to the same private `_fetch_owned_vehicle(vehicle_repo, vehicle_id, current_user)` helper, so the 404/403 logic itself is still deduplicated — only the calling convention differs, driven by whether the route has a body to protect the ordering of.

**6. Rate limits for the newly-covered endpoints mirror the existing precedent (`60/min` via `get_remote_address`), not a stricter per-endpoint number.**
No evidence exists yet of actual abuse patterns to size a tighter limit against, and introducing a second limiting scheme (e.g. per-user instead of per-IP) is a bigger design decision better made with real traffic data. `60/min` is already the project's established default for a sensitive endpoint (`POST /vehicles/{token}/location`) and is applied here to: `POST /vehicles` (register), `PUT /vehicles/{id}` (update, when brand is Toyota), `POST /ser-ticket-providers/connections`, `GET /auth/google/callback`. Known limitation: slowapi's in-memory store is per-process, so this doesn't hold under a multi-replica deployment — out of scope here (same limitation the existing 2 endpoints already have).

**7. Reject-unknown-keys in notification `config` is implemented inside `validate_notification_config()`, mirroring `extra="forbid"` semantics but hand-written.**
`config` is a `dict[str, Any]` because `config_schema` is data-driven (stored per-row in `notification_types`), so it can't be a static Pydantic model with `extra="forbid"`. Add: for each key in `config` not present in `config_schema`, raise `InvalidNotificationConfigError` (same exception the existing type/bounds checks use, so the router's existing `except InvalidNotificationConfigError → 422` handling covers it with no router change). This is a deliberate reversal of the current "ignore extra keys, stay forward-compatible" design — accepted by the project owner as the desired behavior change.

## Risks / Trade-offs

- **[Breaking change for any client sending extra fields today]** → Frontend is the only client; a quick grep of `frontend/src/api/*.ts` request bodies before implementation confirms no legitimate extra fields are sent (tasks.md includes this check).
- **[`config_schema` forward-compatibility loss (decision 7) — a future notification type's caller can no longer "soft" pre-send a field the current backend doesn't understand]** → Accepted trade-off per project owner; the pre-send scenario was theoretical (no evidence anything relied on it), and this codebase deploys backend and frontend together, so "the backend doesn't understand a field yet" isn't really a real-world scenario here the way it might be for a versioned public API.
- **[Defensive `max_length` values (decision 3) are guesses, not verified upstream limits]** → If Toyota's actual username/password limits are ever discovered to be lower (unlikely) or a real display-name UX limit is set later, these are trivial to tighten further; they're a ceiling against abuse, not a UX-driven floor.
- **[Rate-limit `60/min` per IP (decision 6) doesn't distinguish legitimate retries from abuse, and shared-IP users (NAT, corporate proxy) could be affected]** → Same trade-off the existing 2 rate-limited endpoints already accept; not new risk introduced by this change.

## Migration Plan

No data migration. This is a pure application-code change:
1. Add `StrictRequestModel` + switch request models to inherit from it; add field validators/`max_length`; add path-param validation dependencies. Deploy behind the existing CI/test gate — no feature flag needed since behavior only gets *stricter* (a previously-accepted malformed/extra-field request now gets a clean `422` instead of succeeding with silently-dropped data).
2. Add `@limiter.limit("60/minute")` to the four additional endpoints.
3. Add `require_owned_vehicle` dependency, replace inline ownership checks route-by-route.
4. Add reject-unknown-keys to `validate_notification_config()`.
5. Verify frontend sends no extra fields (grep + manual check of the vehicle-register, vehicle-update, preferences, and notification-preferences forms) before merging, since this is the one user-facing behavior change.

Rollback: revert the commit(s); no schema/data changes to unwind.

## Open Questions

- None outstanding — all four threads (schema strictness, field bounds, rate limiting, ownership-check consolidation) and the notification-config behavior change were confirmed with the project owner during exploration.
