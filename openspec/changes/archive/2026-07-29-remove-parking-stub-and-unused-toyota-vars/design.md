## Context

An exploration pass grepped every `.env.example` variable and every domain port/use case/adapter against the rest of `src/` and `tests/` to find code that's declared but never reached at runtime. Two findings survived a direct spot-check (grepping each symbol name across the whole repo):

1. `TOYOTA_USERNAME`, `TOYOTA_PASSWORD`, `DEFAULT_LICENSE_PLATE` — zero `os.environ`/`os.getenv` reads anywhere in `src/`.
2. `ParkingServicePort` → `GetParkingTicketUseCase` → `MadridSerService` — each symbol's only references are to each other; none is imported by `presentation/api/app.py`, any router, the scheduler, or any test outside their own files.
3. `domain/ports/vehicle_provider.py` — the file body is a comment stating it was replaced by `VehiclePullLocationPort` and kept only "as a tombstone."

This is a pure subtraction: nothing currently depends on any of this code, so there is no migration, no data model, and no runtime behavior to preserve.

## Goals / Non-Goals

**Goals:**
- Delete the confirmed-dead env vars, port, use case, and adapter.
- Delete the self-declared tombstone file.
- Keep `README.md`'s env var table in sync (per this repo's mandatory README-consistency rule).
- Leave a clean `git diff` with no behavior change — `make test` and `make lint` must be green exactly as before.

**Non-Goals:**
- `TOYOTA_LOCALE` is explicitly excluded — confirmed live and in active use.
- No change to the real, currently-wired SER ticket flow (`DetermineSerTicketRequirement`, `CreateSerTicket`, `ParkingTicketRepository`, `CityParkingDataProvider`) — that flow already supersedes the code being removed here and is untouched.
- No change to `CityRepository` or `VehiclePullLocationPort` — both are alive and wired, just consumed from infrastructure/presentation rather than an application use case; that's a separate, non-dead-code question and out of scope for this change.

## Decisions

**Delete rather than deprecate.** All three removed symbols are unreachable from any entry point today, so there's no caller to warn or migrate — a deprecation period would only delay the cleanup with no safety benefit.

**Remove empty parent directories left behind, if any.** `infrastructure/parking_services/madrid/` may become empty once `ser_service.py` is deleted; check for other files in that directory before removing it. If `infrastructure/parking_services/` (parent) also has no other providers, it should go too — verify against `provider_registry.py`'s Madrid CSV/shapefile fetchers, which live in the same `parking_services` tree but are a separate, live capability (`SER_ZONE_SHP_URL` etc.) and must NOT be deleted.

**Grep-confirm at deletion time, not just at proposal time.** Between exploration and implementation, other work may land. Tasks must re-run the same grep checks immediately before deleting each symbol, not rely solely on this document's findings.

## Risks / Trade-offs

- **[Risk]** A string-keyed registry or dynamic dispatch could reference `MadridSerService`/`ParkingServicePort` by name rather than direct import, which a plain grep would miss → **Mitigation**: tasks must also grep `provider_registry.py` and any other `ENABLED_*`-style registry for the literal class/module names before deleting, not just direct-import call sites.
- **[Risk]** Deleting `.env.example` lines could break a deployment that still sets these vars (harmless, since they're unread) or scripts/CI that reference them by name → **Mitigation**: grep CI config and `docker-compose.yml` for the three var names before removing them from `.env.example`.
- **[Risk]** Removing `vehicle_provider.py` entirely (rather than leaving the tombstone) could reintroduce the "merge surprise" its own comment warns about, if another branch still references the old `VehicleProviderPort` name → **Mitigation**: grep the working tree (already done — zero hits besides the tombstone file itself) immediately before deleting.

## Migration Plan

Not applicable — no data, no running deployments depend on the removed code. Standard PR review and `make test`/`make lint` gate the change.
