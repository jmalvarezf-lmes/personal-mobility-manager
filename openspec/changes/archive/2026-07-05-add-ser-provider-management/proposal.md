## Why

Users currently have no way to connect a SER ticket provider account through the app — the backend endpoint exists (`POST /ser-ticket-providers/connections`) but there's no UI, no way to check connection status, and no way to disconnect. This change closes that loop: a "SER Providers" page where a user can connect, see status, and disconnect their ElParking account, with a proper server-side logout on disconnect rather than just deleting local data.

## What Changes

- Add `SerTicketProviderPort.logout(session) -> None`, a third port method alongside `login`/`create_ticket`. `ElParkingSerTicketProvider.logout()` calls ElParking's `DELETE /v1/logins/{access_token}`.
- Add `UserSerProviderConfigRepository.delete(user_id, provider)` and `.list_connected_providers(user_id) -> list[str]`.
- Add `DisconnectSerTicketProvider` use case: attempts a best-effort provider-side logout (soft-fails on any provider error or if the provider is currently disabled/unregistered — never blocks the local deletion) and always removes the local session record. Returns whether the provider-side logout succeeded, so the caller can inform the user without treating it as a hard failure.
- Add `ListSerTicketProviderConnections` use case (or similarly named), backing a new `GET /ser-ticket-providers/connections` endpoint returning the list of providers the current user has connected.
- Add `DELETE /ser-ticket-providers/connections/{provider}`, returning `200 {"logout_succeeded": bool}` (not `204`, since the body needs to carry the soft-failure signal).
- Add a "SER Providers" page (protected route), listing known providers (ElParking today) with connection status, a connect modal (mirrors `AddVehicleModal`), and a disconnect action that surfaces a soft warning if provider-side logout failed but still completes the disconnect.
- Add "SER Providers" as a fourth item in the account dropdown (My Vehicles / Preferences / SER Providers / Logout).
- Add a provider icon/logo image to each row on the SER Providers page, purely a frontend visual — not part of the API, domain model, or any stored data. The image is a locally-hosted static asset (`frontend/public/provider-logos/{provider}.webp`), not hotlinked from a third party, since app icons are typically copyrighted by their owner; if the asset is missing, the row degrades gracefully (icon hidden, no broken-image placeholder).

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ser-ticket-provider`: gains a `logout` port method, connection-listing and deletion at the repository level, disconnect/list use cases, two new HTTP endpoints, and the frontend page/nav entry to manage connections. All additive — no existing requirement's behavior changes (the existing `POST /ser-ticket-providers/connections` endpoint and its use case are untouched).

## Impact

- **Backend**: new port method (breaking for any future `SerTicketProviderPort` implementer — only `ElParkingSerTicketProvider` exists today, so blast radius is one file), two new repository methods + Postgres implementation, two new use cases, two new endpoints.
- **API surface**: `GET /ser-ticket-providers/connections`, `DELETE /ser-ticket-providers/connections/{provider}` (both protected).
- **Frontend**: new page, new nav entry, new i18n keys, new API client functions, new Playwright coverage.
- **Assumption to verify during implementation**: ElParking's logout endpoint may require `Authorization: Bearer {access_token}` in addition to the token in the path — not explicitly confirmed in the available docs, isolated as a single assumption the same way the login status-code guess was in the previous change.
