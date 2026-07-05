## 1. Domain layer

- [x] 1.1 Add `logout(self, session: SerProviderSession) -> None` abstract method to `domain/ports/ser_ticket_provider.py`
- [x] 1.2 Add `delete(self, user_id: UUID, provider: str) -> None` and `list_connected_providers(self, user_id: UUID) -> list[str]` abstract methods to `domain/ports/user_ser_provider_config_repository.py`

## 2. Infrastructure layer

- [x] 2.1 `infrastructure/ser_ticket_providers/elparking/provider.py` — implement `logout(session)`: extract `access_token` from `session.data`, `DELETE {base_url}/v1/logins/{access_token}` with `Authorization: Bearer {access_token}` header, using the same synchronous `httpx.Client` pattern as `login`. Wrap `httpx.HTTPError`/non-2xx as `SerProviderApiError`. Flag the `Authorization` header as an assumption in a code comment (mirroring the `_INVALID_CREDENTIALS_STATUS_CODE` comment style already in this file) — not confirmed against the live API by the docs available.
- [x] 2.2 `infrastructure/repositories/postgres/user_ser_provider_config_repo.py` — implement `delete` (DELETE by `(user_id, provider)`, no error if no row matched) and `list_connected_providers` (SELECT `provider` WHERE `user_id = ...`)

## 3. Application layer

- [x] 3.1 `application/use_cases/disconnect_ser_ticket_provider.py` — `DisconnectSerTicketProvider`: `execute(user_id, provider) -> bool`. If no session exists, return `True` immediately. Otherwise resolve the provider instance from the injected `providers: dict[str, SerTicketProviderPort]`; if absent, treat as logout failure; if present, call `provider.logout(session)` and catch `SerProviderApiError` as a soft failure (do not re-raise). Always call `config_repo.delete(user_id, provider)` regardless of logout outcome. Return whether logout succeeded.
- [x] 3.2 `application/use_cases/list_ser_ticket_provider_connections.py` — `ListSerTicketProviderConnections`: `execute(user_id) -> list[str]`, delegating to `config_repo.list_connected_providers(user_id)`

## 4. Wiring — app.py

- [x] 4.1 Construct `DisconnectSerTicketProvider` and `ListSerTicketProviderConnections` alongside the existing `connect_ser_ticket_provider`/`create_ser_ticket` wiring, store on `app.state`

## 5. Presentation layer — schemas and router

- [x] 5.1 Add response schemas to `presentation/api/schemas.py`: `SerTicketProviderConnectionsResponse` (`providers: list[str]`), `DisconnectSerTicketProviderResponse` (`logout_succeeded: bool`)
- [x] 5.2 Update `presentation/api/routers/ser_ticket_providers.py`:
  - `GET /ser-ticket-providers/connections`, `Depends(get_current_user)`, returns `SerTicketProviderConnectionsResponse(providers=...)`
  - `DELETE /ser-ticket-providers/connections/{provider}`, `Depends(get_current_user)`, calls `DisconnectSerTicketProvider.execute`, returns `200` with `DisconnectSerTicketProviderResponse(logout_succeeded=...)` — explicitly not `204`

## 6. Backend tests

- [x] 6.1 Extend `tests/infrastructure/test_elparking_provider.py` — `logout` sends the correct `DELETE` URL and `Authorization` header; failure (non-2xx, connection error) raises `SerProviderApiError`
- [x] 6.2 Extend `tests/infrastructure/test_user_ser_provider_config_repo_integration.py` (or equivalent) — `delete` removes an existing row and is idempotent when none exists; `list_connected_providers` reflects stored rows and returns `[]` for a user with none
- [x] 6.3 `tests/application/use_cases/test_disconnect_ser_ticket_provider.py` — covers all four scenarios from the spec: successful logout, logout failure (soft), unregistered provider (soft), already-disconnected (no-op success) — verify `config_repo.delete` is called in every case except when no session existed to begin with (still fine to call, but assert on the meaningful behavior per spec)
- [x] 6.4 `tests/application/use_cases/test_list_ser_ticket_provider_connections.py` — returns whatever the repo reports
- [x] 6.5 Extend `tests/presentation/test_ser_ticket_providers_router.py` — `GET .../connections` returns the right list (and empty list) for authenticated users, 401 for anonymous; `DELETE .../connections/{provider}` returns 200 with the correct `logout_succeeded` value in both outcomes, 401 for anonymous without contacting anything

## 7. Frontend — API client and page

- [x] 7.1 `frontend/src/api/serTicketProviders.ts` — `getConnections(): Promise<{providers: string[]}>`, `connect(payload: {provider, email, password}): Promise<void>`, `disconnect(provider: string): Promise<{logout_succeeded: boolean}>` — mirror `frontend/src/api/preferences.ts`'s fetch/error-handling style
- [x] 7.2 `frontend/src/pages/SerProvidersPage.tsx` — new page:
  - Hardcoded list of known providers (`["elparking"]` for now, mirroring `AddVehicleModal`'s brand-option hardcoding convention)
  - On mount, calls `getConnections()` and cross-references against the known-provider list to render each row's status
  - "Connect" button per not-yet-connected row opens a connect modal (email + password fields, mirrors `AddVehicleModal`'s structure/validation/error display)
  - "Disconnect" button per connected row: `window.confirm(...)` (mirrors `VehicleCard.handleDelete`'s confirmation pattern) → calls `disconnect(provider)` → updates the row's status; if `logout_succeeded: false`, show a non-blocking warning message (does not treat the disconnect as failed)
- [x] 7.3 Add protected route `/ser-providers` in `App.tsx`, wrapped in `ProtectedRoute` like the other authenticated pages
- [x] 7.4 Add a provider icon to each row in `SerProviderRow.tsx`: `<img src="/provider-logos/{provider}.webp">` with `onError` hiding it gracefully (no broken-image placeholder) if the asset is missing. Purely presentational — no API/domain/data changes. `frontend/public/provider-logos/elparking.webp` needs to be supplied by the project owner (not hotlinked from a third party, since app icons are typically copyrighted) — until it's placed there, the row simply renders without the icon.

## 8. Frontend — nav and i18n

- [x] 8.1 Add "SER Providers" as a fourth item in `Nav.tsx`'s account dropdown (alongside My Vehicles, Preferences, Logout)
- [x] 8.2 Add i18n keys to `frontend/public/locales/en/translation.json` and `es/translation.json`: `nav.serProviders`, and a `page.serProviders` section (title, connect/disconnect button labels, connected/not-connected status labels, the soft-warning message for unconfirmed logout, modal field labels/errors)

## 9. Frontend — Playwright tests

- [x] 9.1 Add `frontend/e2e/pages/SerProvidersPage.ts` POM (provider rows, connect modal fields, connect/disconnect buttons, status labels, warning message), following `MyVehiclesPage.ts`'s constructor/locator conventions
- [x] 9.2 Update `frontend/e2e/pages/NavPage.ts` to include the new "SER Providers" link locator
- [x] 9.3 `frontend/e2e/ser-providers.spec.ts` (mocking `GET`/`POST`/`DELETE /api/ser-ticket-providers/connections*`, following the route-mocking style in `my-vehicles.spec.ts`/`preferences.spec.ts`):
  - unauthenticated visitor redirected from `/ser-providers` to `/`
  - not-connected provider shows a Connect action; connecting updates status without a manual refresh
  - connected provider shows a Disconnect action; disconnecting with `logout_succeeded: true` removes the connected status cleanly
  - disconnecting with `logout_succeeded: false` still shows the provider as disconnected, plus the non-blocking warning message
- [x] 9.4 Extend the nav coverage (`nav.spec.ts` or the `my-vehicles.spec.ts` Navigation block) to include the SER Providers link in the dropdown's expected contents

## 10. Verification

- [x] 10.1 Run backend test suite and linters (ruff, mypy)
- [x] 10.2 Run frontend lint/typecheck/build
- [x] 10.3 Run the full Playwright suite, confirm no regressions from the nav/dropdown change
- [x] 10.4 Manually verified `DELETE /ser-ticket-providers/connections/{provider}` end-to-end against the live ElParking API — disconnection works, confirming the `Authorization: Bearer` header assumption for logout (task 2.1).
