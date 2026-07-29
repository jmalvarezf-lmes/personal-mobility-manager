## 1. Re-verify dead code before deleting

- [x] 1.1 Re-grep `TOYOTA_USERNAME`, `TOYOTA_PASSWORD`, `DEFAULT_LICENSE_PLATE` across `src/`, `tests/`, `docker-compose.yml`, and any CI config to confirm still zero reads
- [x] 1.2 Re-grep `ParkingServicePort`, `GetParkingTicketUseCase`, `MadridSerService` across the full repo (including `infrastructure/parking_services/provider_registry.py` and `infrastructure/ser_ticket_providers/registry.py`, both of which use string-keyed registries elsewhere) to confirm no dynamic/string-based reference exists
- [x] 1.3 Confirm `domain/ports/vehicle_provider.py` still has zero references beyond its own tombstone comment

## 2. Remove unused env vars

- [x] 2.1 Remove `TOYOTA_USERNAME`, `TOYOTA_PASSWORD`, `DEFAULT_LICENSE_PLATE` lines from `.env.example`
- [x] 2.2 Remove the corresponding row from `README.md`'s environment variable table

## 3. Remove the dead parking-service stub chain

- [x] 3.1 Delete `src/mobility_manager/infrastructure/parking_services/madrid/ser_service.py`
- [x] 3.2 Delete `src/mobility_manager/application/use_cases/get_parking_ticket.py`
- [x] 3.3 Delete `src/mobility_manager/domain/ports/parking_service.py`
- [x] 3.4 Check `src/mobility_manager/infrastructure/parking_services/madrid/` for other files; if `ser_service.py` was the only file, remove the now-empty directory (do NOT remove `provider_registry.py`'s Madrid CSV/shapefile fetchers — those are a separate, live capability)
- [x] 3.5 Delete any test file exclusively covering `MadridSerService`, `GetParkingTicketUseCase`, or `ParkingServicePort`, if one exists

## 4. Remove the tombstone file

- [x] 4.1 Delete `src/mobility_manager/domain/ports/vehicle_provider.py`

## 5. Verify

- [x] 5.1 Run `make lint` — must pass with no new findings
- [x] 5.2 Run `make test` — must pass with no regressions (integration tests skip without `POSTGRES_DSN`, per project convention)
- [x] 5.3 Run `make coverage` — `domain/` and `application/` must stay at their required minimums (100% / 80%) now that dead modules are gone
- [x] 5.4 Grep the whole repo once more for the three env var names and the three deleted symbol names to confirm zero remaining references outside this change's own git history
