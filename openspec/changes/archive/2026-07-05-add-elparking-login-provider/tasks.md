## 1. Domain layer

- [x] 1.1 Add `SerProviderAuthenticationError` and `SerProviderApiError` to `domain/exceptions.py`, following the existing `class XError(Exception): pass` style

## 2. Infrastructure layer — ElParking provider

- [x] 2.1 `infrastructure/ser_ticket_providers/elparking/__init__.py` and `infrastructure/ser_ticket_providers/elparking/provider.py` — `ElParkingSerTicketProvider(SerTicketProviderPort)`:
  - Module-level constant `_EP_APP_NAME = "elparking"` (hardcoded); base URL and app version come from config accessors (see 2.2, 2.3)
  - `login(self, credentials: SerProviderCredentials) -> SerProviderSession`: build request body from `credentials.data` (`email`, `password`, and `uid`/`model` if present), POST to `{base_url}/v1/logins` with headers `Content-Type: application/json`, `ep-app-name: elparking`, `ep-app-version: <get_elparking_app_version()>`, using a synchronous `httpx.Client(timeout=...)` (mirror `MadridCallejeroCsvFetcher`'s sync client style, not the async pattern in `auth.py`)
  - On a response indicating invalid credentials, raise `SerProviderAuthenticationError` — during implementation, hit the real API (or its docs/support) to confirm the exact status code(s) ElParking returns for wrong email/password, since the provided docs don't specify this explicitly; don't guess a status code without verifying
  - On any other non-2xx response, unexpected/malformed body, or `httpx.HTTPError` (connection failure, timeout), raise `SerProviderApiError` — do not let raw `httpx` exceptions propagate out of this method
  - On success, return `SerProviderSession(data={"access_token": <response's "access_token">, "device_session_id": <response's "id">})` — nothing else from the response body
  - `create_ticket(self, session, vehicle, duration_minutes) -> ParkingTicket`: raise `NotImplementedError("ElParking ticket creation is not yet implemented")`

- [x] 2.2 Add `get_elparking_base_url() -> str` to `config.py`: reads `ELPARKING_API_BASE_URL` with **no default** (mirror `get_encryption_key()`'s pattern — raise `RuntimeError` with a clear, actionable message if unset). The real base URL is not yet known (the provided docs only show a placeholder, `https://api.example.com`), so there is deliberately no fallback to guess at — this must be supplied via environment variable in every deployment that enables ElParking.

- [x] 2.3 Add `get_elparking_app_version() -> str` to `config.py`: reads `ELPARKING_APP_VERSION`, **default `"26.2"`** (unlike the base URL, this has a sensible default since it's expected to evolve over time rather than gate whether the provider can be enabled). `ElParkingSerTicketProvider.login()` uses this for the `ep-app-version` header instead of a hardcoded value.

## 3. Infrastructure layer — registry wiring

- [x] 3.1 Add `get_enabled_ser_providers() -> list[str]` to `config.py`, mirroring `get_enabled_brands()`'s shape: parse comma-separated `ENABLED_SER_PROVIDERS` env var, default `"elparking"` (unlike `get_enabled_brands()`, which defaults to `"generic"` — ElParking is meant to be on by default)
- [x] 3.2 Update `infrastructure/ser_ticket_providers/registry.py`: `SerTicketProviderRegistry.build_providers()` now reads `ENABLED_SER_PROVIDERS` directly via `os.environ.get("ENABLED_SER_PROVIDERS", "elparking")` (self-contained parsing, mirroring `BrandRegistry.build_pull_providers()`'s own direct `os.environ.get("ENABLED_BRANDS", ...)` — not routed through the config.py helper, consistent with that existing precedent). When `"elparking"` is among the enabled codes, validate both `os.environ.get("ENCRYPTION_KEY")` and `os.environ.get("ELPARKING_API_BASE_URL")` are set and raise `RuntimeError` immediately if either is missing (mirror `BrandRegistry`'s exact Toyota check — same error-message style; both are required config for enabling ElParking, not just the encryption key), then instantiate and register `ElParkingSerTicketProvider` under key `"elparking"`. Unknown provider codes are skipped with a warning log, mirroring `BrandRegistry`'s handling of unknown brand codes.

## 4. Wiring — app.py

- [x] 4.1 Update the "SER ticket provider (no HTTP surface yet)" section in `presentation/api/app.py`: the current comment and try/except around `get_encryption_key()` assumes no provider is ever registered — that assumption is now false (`ENABLED_SER_PROVIDERS` defaults to `"elparking"`). Replace the lenient try/except with the same non-swallowing pattern used for Toyota (`if Brand.TOYOTA in enabled_brands: encryption_key = get_encryption_key()` — no try/except, real `RuntimeError` propagates and crashes startup): compute whether ElParking is enabled via `get_enabled_ser_providers()`, and if so, call `get_encryption_key()` without catching `RuntimeError`. Update the stale comment accordingly.
- [x] 4.2 Update the section header comment "SER ticket provider (no HTTP surface yet)" since this change adds one — remove the "(no HTTP surface yet)" qualifier or update it to reflect reality once the router is wired (see task 6.3)

## 5. Presentation layer — schema and factory

- [x] 5.1 Add `ConnectElParkingRequest` to `presentation/api/schemas.py`: `provider: Literal["elparking"]`, `email: EmailStr`, `password: str` (mirror `RegisterToyotaRequest`'s field-validation style — check length constraints against ElParking's documented limits: email 6-100 chars, password 1-100 chars). If a discriminated union type alias is used elsewhere for vehicle registration (`RegisterVehicleRequest`), mirror that same pattern for a new `ConnectSerTicketProviderRequest` union type (currently only one variant, `ConnectElParkingRequest`, but the union shape keeps the door open for a second provider later without changing the endpoint's request contract)
- [x] 5.2 Add `SerTicketProviderConnectFactory` to `presentation/api/factories.py`: `build(body: ConnectElParkingRequest, user_id: UUID) -> SerProviderCredentials`, returning `SerProviderCredentials(data={"email": body.email, "password": body.password, "uid": str(user_id), "model": "personal-mobility-manager-server"})` for the `elparking` case (mirror `VehicleRegisterFactory`'s per-brand dispatch style if/when a second provider variant is added)

## 6. Presentation layer — router

- [x] 6.1 Add `SerTicketProviderConnectionResponse` if needed, or confirm `204 No Content` requires no response schema (check `Response` usage pattern in `vehicles.py` for the no-body-response convention already used there)
- [x] 6.2 `presentation/api/routers/ser_ticket_providers.py` — new router:
  - `POST /ser-ticket-providers/connections`, `Depends(get_current_user)`, accepts the request body from task 5.1
  - Builds `SerProviderCredentials` via `SerTicketProviderConnectFactory.build(body, current_user.id)`
  - Calls `request.app.state.connect_ser_ticket_provider.execute(current_user.id, body.provider, credentials)`
  - Catches `SerProviderAuthenticationError` → `HTTPException(401, ...)`; `SerProviderApiError` → `HTTPException(502, ...)`; `SerTicketProviderNotFoundError` → `HTTPException(404, ...)`
  - Returns `204 No Content` on success
- [x] 6.3 Register `ser_ticket_providers_router` in `app.py` (`app.include_router(...)`)

## 7. Backend tests

- [x] 7.1 `tests/infrastructure/test_elparking_provider.py` — unit tests for `ElParkingSerTicketProvider.login`, using a mocked `httpx` transport (`httpx.MockTransport`, consistent with testing an httpx-based client without real network calls): successful login returns the minimal session (`access_token` + `device_session_id` only, even if the mocked response includes more fields); `ep-app-version` header defaults to `"26.2"` and honors `ELPARKING_APP_VERSION` when set; invalid-credentials response raises `SerProviderAuthenticationError`; 5xx/429/malformed-body/connection-error responses raise `SerProviderApiError`; `create_ticket` raises `NotImplementedError` without making any HTTP call
- [x] 7.2 `tests/infrastructure/test_ser_ticket_provider_registry.py` (or extend existing coverage if it exists) — default `ENABLED_SER_PROVIDERS` registers `"elparking"`; explicitly disabling it removes the entry; missing `ENCRYPTION_KEY` with ElParking enabled raises `RuntimeError` at `build_providers()` time
- [x] 7.3 `tests/presentation/test_ser_ticket_provider_connect_factory.py` — factory injects `uid=str(user_id)` (not random) and the fixed `model` string
- [x] 7.4 `tests/presentation/test_ser_ticket_providers_router.py` — successful connection returns 204 and persists a session (fake `ConnectSerTicketProvider`/use-case double); `SerProviderAuthenticationError` → 401; `SerProviderApiError` → 502; unknown provider → 404; anonymous request → 401 without contacting anything

## 8. Verification

- [x] 8.1 Run backend test suite and linters (ruff, mypy) per project convention
- [x] 8.2 Confirm `ENCRYPTION_KEY` is documented as required in any deployment/env-var reference this project maintains (e.g. `.env.example`, README), since ElParking being enabled by default now makes it a hard startup requirement, not an optional one
- [x] 8.3 Manually verified `POST /ser-ticket-providers/connections` end-to-end against the live ElParking API — confirmed working with the real `ELPARKING_API_BASE_URL` and the updated `ELPARKING_APP_VERSION` default.

  **NOT VERIFIED — left unchecked.** No ElParking test credentials or confirmed real base URL were available in this environment (a sandbox with no network access to any live ElParking host). `ElParkingSerTicketProvider.login()`'s invalid-credentials detection currently assumes HTTP `401` for rejected credentials — this is an isolated, clearly-commented, easy-to-change assumption in `src/mobility_manager/infrastructure/ser_ticket_providers/elparking/provider.py` (`_INVALID_CREDENTIALS_STATUS_CODE`), not confirmed against the live API. Coverage for this behavior relies entirely on the `httpx.MockTransport`-based unit tests in `tests/infrastructure/test_elparking_provider.py` (task 7.1). Before relying on this in production, run a manual wrong-password request against the real ElParking API and adjust `_INVALID_CREDENTIALS_STATUS_CODE` if the observed status code differs.
