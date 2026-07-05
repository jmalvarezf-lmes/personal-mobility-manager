## Context

`SerTicketProviderPort`, `SerTicketProviderRegistry`, `SerProviderCredentials`/`SerProviderSession`, and the `ConnectSerTicketProvider`/`CreateSerTicket` use cases already exist (from `add-ser-ticket-provider-interface`), but nothing concrete implements the port and the registry always returns an empty mapping. This change adds the first real provider — ElParking — and, because there's now something real to connect to, the first real HTTP endpoint on top of `ConnectSerTicketProvider`.

ElParking's login API (`POST /v1/logins`) issues a `access_token` that "never expires by itself" and can only be revoked by explicit logout — this removes the token-renewal concern the interface design deliberately deferred as "provider-dependent." For ElParking specifically, there is no renewal logic to write.

`create_ticket`'s API spec is not yet available, so `ElParkingSerTicketProvider.create_ticket()` is a documented `NotImplementedError` stub in this change; a concrete ticket-creation implementation is explicitly a separate future change.

## Goals / Non-Goals

**Goals:**
- Implement `ElParkingSerTicketProvider.login()` against the documented ElParking API, using a synchronous `httpx.Client` (consistent with `MadridCallejeroCsvFetcher`'s existing sync pattern — no async is needed since `SerTicketProviderPort.login` is a plain sync method).
- Give `SerTicketProviderPort` its first real failure contract: `SerProviderAuthenticationError` for invalid credentials, `SerProviderApiError` for everything else (rate limiting, 5xx, unexpected response shape).
- Make `SerTicketProviderRegistry` do real work: register `ElParkingSerTicketProvider` when enabled via `ENABLED_SER_PROVIDERS` (default `"elparking"`), fail fast at startup if enabled without `ENCRYPTION_KEY`.
- Add `POST /ser-ticket-providers/connections`, a protected endpoint that lets a logged-in user submit ElParking credentials and get a clear success/failure result.
- Store only what's needed for future ticket creation: `access_token` and the device-session `id`.

**Non-Goals:**
- `create_ticket` implementation — separate future change.
- Any frontend UI for connecting an account — the endpoint exists, nothing calls it yet.
- Session renewal/refresh logic — not needed for ElParking (see Context).
- Solving ElParking's IP-based rate limiting across concurrent user connections — noted as an operational risk, not mitigated here (see Risks).

## Decisions

### 1. Synchronous httpx.Client, no async
`SerTicketProviderPort.login`/`create_ticket` are plain synchronous methods — there was never an async requirement, unlike Toyota's adapter, which only uses `asyncio.run()` because `pytoyoda` itself is async internally. ElParking is a plain REST API called directly, so `ElParkingSerTicketProvider` uses `httpx.Client(timeout=...)` synchronously, mirroring `MadridCallejeroCsvFetcher.fetch()`'s existing pattern rather than the async `httpx.AsyncClient` pattern used in the OAuth callback route (that route is async because it's a FastAPI handler, not because the port demands it).

### 2. Dedicated exceptions: `SerProviderAuthenticationError` and `SerProviderApiError`
`VehiclePullLocationPort.fetch_location` has no dedicated auth-failure exception (its docstring just says "Exception: On network/auth failures"), but nothing has actually called it in anger for a user-facing flow the way this endpoint will. Two exceptions:
- `SerProviderAuthenticationError`: ElParking returned a response indicating bad credentials (expected to map to a 401/422-style response — exact status codes depend on testing against the real API, but the domain exception is unambiguous regardless).
- `SerProviderApiError`: anything else — network failure, unexpected status code, malformed response body, 429 rate-limit.

This lets the new router return a genuinely different message for "check your password" versus "ElParking is having issues, try later," which a single generic exception couldn't support. `ElParkingSerTicketProvider.login()` raises `SerProviderAuthenticationError` for the credential-rejection case and `SerProviderApiError` for everything else (including `httpx.HTTPError` from connection failures — caught and re-raised as `SerProviderApiError`, not left as a raw `httpx` exception leaking out of the infrastructure layer).

### 3. Session payload: `access_token` + device-session `id` only
Per ElParking's docs, the token alone identifies the user for every subsequent `SecurityRestController`-based call — the nested `user` object in the login response is redundant with data this codebase already has in its own `users` table. `SerProviderSession.data = {"access_token": str, "device_session_id": int}`. Nothing else is captured. If `create_ticket`'s future spec needs more, `data` can be widened then — it's already an opaque dict, so this costs nothing to revise later.

### 4. `uid`/`model` — stable per-user identity, honest model string
ElParking's `uid` field feeds their device/fraud-tracking (`DeviceSessionFraudBlocker`). Sending a fresh random string per login attempt (as their own docs example does — `"uid": "tralara"`) would make every user look like a new, suspicious "device" logging in from the same server IP. Instead: `uid = str(user_id)` (stable across repeated logins for the same user, harmless since it's not a secret) and `model = "personal-mobility-manager-server"` (honestly identifies this as a server integration, not a spoofed device).

### 5. Where `uid`/`model` get set: the presentation-layer factory, not the use case or the provider
`ConnectSerTicketProvider.execute(user_id, provider, credentials)` is provider-agnostic — it doesn't know "uid" is an ElParking concept, and shouldn't. `ElParkingSerTicketProvider.login()` only receives whatever's inside `credentials.data` — it has no independent access to `user_id`. So the only place that has both the current user's id and knowledge of which provider-specific request shape was submitted is the presentation layer, at the point `SerProviderCredentials` is first constructed. A new `SerTicketProviderConnectFactory` (mirroring `VehicleRegisterFactory`'s role) builds `SerProviderCredentials(data={"email": ..., "password": ..., "uid": str(user_id), "model": "personal-mobility-manager-server"})` from the validated request body plus `current_user.id`.

### 6. `ep-app-name` is a hardcoded provider constant; `ep-app-version` is env-configurable
`elparking` is the most semantically correct of the three valid `ep-app-name` values (`parkingdoor`, `elparking`, `plock`) for identifying as the ElParking client itself — this isn't deployment config, it's a fixed characteristic of how this specific provider class talks to this specific API, so it stays a hardcoded constant inside `ElParkingSerTicketProvider`.

`ep-app-version`, however, is expected to evolve over time as this integration matures (unlike the app name, which never changes), so it's read from a new `ELPARKING_APP_VERSION` environment variable via `config.get_elparking_app_version()`, defaulting to `"26.2"`. Unlike `ELPARKING_API_BASE_URL`, this has a sensible default rather than being required — it's meant to be bumped over time, not to gate whether the provider can be enabled at all.

### 7. `POST /ser-ticket-providers/connections` — REST-shaped, discriminated request body
Mirrors the existing `POST /vehicles` convention (`RegisterToyotaRequest | RegisterGenericRequest` discriminated by a `brand` field, resolved via `VehicleRegisterFactory`) rather than inventing a per-provider path (`/connect/{provider}`) or a generic untyped body. `ConnectElParkingRequest(provider: Literal["elparking"], email: EmailStr, password: str)` is the first (and only, for now) variant; adding a second provider later means adding a second typed request variant and extending the factory's dispatch, exactly like adding a new vehicle brand does today. The endpoint is named `connections` (not `connect`) to stay noun-based/REST-shaped — POST creates a connection resource.

Responses: `204 No Content` on success (nothing needs to flow back to the frontend — the access token stays server-side); `401` on `SerProviderAuthenticationError`; `502` on `SerProviderApiError`.

### 8. Registry: env-var gated, fail-fast on missing encryption key
`SerTicketProviderRegistry.build_providers()` reads `ENABLED_SER_PROVIDERS` (comma-separated, default `"elparking"` — unlike `ENABLED_BRANDS`, which defaults to `"generic"`, since ElParking is the only provider and is meant to be on by default). Mirrors `BrandRegistry`'s Toyota check: if `"elparking"` is enabled and `ENCRYPTION_KEY` is not set, raise `RuntimeError` at startup rather than failing lazily on a user's first connection attempt.

## Risks / Trade-offs

- **[Risk] ElParking's login is IP-rate-limited, and every user's "connect account" attempt originates from this backend's single server IP.** → Not mitigated in this change; if it becomes a real problem (multiple users connecting around the same time triggering ElParking's `IpRateLimiter`), a future change would need client-side throttling/queueing on our side. For now, a `SerProviderApiError` from a 429 surfaces as a generic "try again later" to the user, which is at least not a crash.
- **[Risk] Exact ElParking status codes for "bad credentials" vs. other failures aren't confirmed against the live API yet** (the docs describe the happy path and the domain-check 403, but not the precise wrong-password response). → Mitigation: `ElParkingSerTicketProvider.login()`'s status-code-to-exception mapping should be validated against the real API during implementation/testing, not assumed from docs alone; treat anything not clearly identifiable as a credential rejection as `SerProviderApiError` (fail toward the more generic, safer bucket).
- **[Trade-off] No frontend UI ships with this change** — the endpoint is real but unreachable from the app. Accepted since there's nothing to build a UI for get yet (create_ticket isn't implemented), and building a UI now would be speculative.

## Migration Plan

1. Deploy backend changes. `ENABLED_SER_PROVIDERS` defaults to `"elparking"`, so ElParking becomes active on deploy — ensure `ENCRYPTION_KEY` is set in every environment before deploying (startup will fail loudly otherwise, which is the intended fail-fast behavior).
2. No database migration needed — `user_ser_provider_configs` already exists from the interface change.
3. Rollback: revert the code change; no data migration to undo since nothing writes to `user_ser_provider_configs` until a real user calls the new endpoint.

## Open Questions

None outstanding.
