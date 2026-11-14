## Why

ElParking validates the `ep-app-version` header against its current mobile app releases, so every release forces us to update `ELPARKING_APP_VERSION` to keep the integration alive. Adding `ep-app-os: web` tells ElParking to treat this client as the web channel and skip version checking, removing the recurring release-toil without changing the rest of the header contract.

## What Changes

- Add a hardcoded `ep-app-os: web` header to every ElParking HTTP call made by `ElParkingClient`, alongside the existing `ep-app-name` and `ep-app-version` headers.
- Keep `ep-app-name: elparking` and `ep-app-version` (still sourced from `ELPARKING_APP_VERSION`) unchanged for backward compatibility.
- Update `ElParkingClient` unit tests to assert the new header is present on login, logout, and every authenticated call.
- Update the `ser-ticket-provider` capability spec to require the `ep-app-os` header.

## Capabilities

### New Capabilities

_None — this is a delta to an existing capability._

### Modified Capabilities

- `ser-ticket-provider`: ElParking HTTP calls must now include the `ep-app-os: web` header in addition to the existing `ep-app-name`/`ep-app-version` headers.

## Impact

- `src/mobility_manager/infrastructure/ser_ticket_providers/elparking/client.py` — adds the new header to `_auth_headers()`.
- `tests/infrastructure/test_elparking_client.py` — updates header assertions.
- `openspec/specs/ser-ticket-provider/spec.md` — delta spec updates the ElParkingClient header requirement.
- No API, database, or domain-model changes. No migration needed.
