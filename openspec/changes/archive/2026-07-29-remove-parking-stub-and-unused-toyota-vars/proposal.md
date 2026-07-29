## Why

A dead-code audit found configuration and code paths that are declared but never read or called anywhere in the codebase: two Toyota credential env vars, an unused default-license-plate env var, and a whole port → use case → adapter chain that was superseded by the current SER ticket flow but never deleted. Removing them stops new contributors (and future audits) from re-investigating code that looks live but isn't, and removes credential-shaped env vars that invite confusion about where Toyota credentials actually come from (they are entered per-user on the vehicles page and encrypted with `ENCRYPTION_KEY`, not read from process env).

## What Changes

- **BREAKING**: Remove `TOYOTA_USERNAME`, `TOYOTA_PASSWORD`, and `DEFAULT_LICENSE_PLATE` from `.env.example` — none are read anywhere in `src/` (confirmed by grep across the full codebase); Toyota credentials are supplied per-vehicle through the API, not via process env.
- Remove the entire unused parking-service stub chain:
  - `src/mobility_manager/domain/ports/parking_service.py` (`ParkingServicePort`, empty body)
  - `src/mobility_manager/application/use_cases/get_parking_ticket.py` (`GetParkingTicketUseCase`, empty body)
  - `src/mobility_manager/infrastructure/parking_services/madrid/ser_service.py` (`MadridSerService`, the only implementation of `ParkingServicePort`)
  - Any now-empty parent directories left behind by this removal
- Remove the self-declared tombstone file `src/mobility_manager/domain/ports/vehicle_provider.py` (already documented in its own docstring as dead, replaced by `VehiclePullLocationPort`)
- Update `README.md`'s environment variable table to drop the now-deleted rows for `TOYOTA_USERNAME`, `TOYOTA_PASSWORD`, and `DEFAULT_LICENSE_PLATE`.

Out of scope: `TOYOTA_LOCALE` is NOT touched — investigation during exploration confirmed it is live (read by `get_toyota_locale()`, served via `GET /config`, and used as the default locale on vehicle creation). The reason it appears to default to `es-ES` instead of the code-level `en_GB` fallback is that `.env.example` ships `TOYOTA_LOCALE=es-es` as a non-empty example value, unlike its now-removed siblings which ship empty.

## Capabilities

### New Capabilities
- `codebase-hygiene`: Formalizes the invariant this cleanup establishes — `.env.example` only lists variables actually read by the application, and domain ports/use cases/adapters are only kept while they have a real consumer. This is a documentation of a repo-hygiene contract, not a runtime feature.

### Modified Capabilities
(none — the removed code was never wired into any router, scheduler, or consumer, so it was never covered by an existing spec; `vehicle-registry`'s existing requirement that Toyota credentials come from the request body, not process env, is unaffected since it never mentioned these dead env vars)

## Impact

- **Affected code**: `domain/ports/parking_service.py`, `domain/ports/vehicle_provider.py`, `application/use_cases/get_parking_ticket.py`, `infrastructure/parking_services/madrid/ser_service.py`, `.env.example`, `README.md`.
- **Affected tests**: any test file exclusively exercising the removed classes (none found referencing them beyond their own definitions during the audit, but tasks must re-verify before deletion).
- **No API, schema, or DB impact**: none of the removed code is reachable from any FastAPI router, scheduler, or CLI entry point today.
- **No config/deployment impact** beyond `.env.example` losing three unused, always-blank-or-unread keys.
