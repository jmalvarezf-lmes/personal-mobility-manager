## Why

`SerZone.contains()` uses shapely's boundary-inclusive `covers()` with zero tolerance. A live incident (2026-07-24) showed a parked vehicle's GPS fix land 3.68cm outside a SER zone's polygon: `find_containing()` returned `None`, so the `ser_zone_ticket_required` notification never fired — even though `GET /parking/ser-zone` (a different code path, `find_nearest()`) reported `distance_meters: 0`, making the zone look entered. GPS positioning error routinely exceeds several metres (the zone polygons themselves are already buffered generously for this reason, per `add-ser-zone-boundaries` design.md D4), so a strict zero-tolerance edge check produces false negatives for genuinely-parked-in-zone vehicles. `find_containing()` also backs `ElParkingSerTicketProvider.create_ticket()`'s zone resolution, so the same false negative can block ticket creation, not just notifications.

## What Changes

- Add a `tolerance_m: float = 0.0` parameter to `SerZone.contains()`: returns `True` if the location is covered by the polygon OR within `tolerance_m` metres of its boundary. Default of `0.0` preserves exact current behavior for any caller that doesn't pass a tolerance (including existing domain unit tests).
- `PostgresSerZoneRepository.find_containing()` reads a configurable tolerance and passes it to every `zone.contains()` check, so both of `find_containing()`'s callers — `FindContainingSerZone` (notification path) and `ElParkingSerTicketProvider.create_ticket()` (ticket-creation path) — get the wider check automatically, with no change needed at either call site.
- Add `get_ser_zone_containment_tolerance_cm() -> int` to `config.py`, reading a new `SER_ZONE_CONTAINMENT_TOLERANCE_CM` environment variable (integer centimetres, default `50`), following the existing int-with-fallback env-var pattern (e.g. `get_vehicle_poll_interval_minutes()`). The repository converts centimetres to metres at the point of use; `SerZone.contains()`'s domain math stays in metres (matching its UTM geometry), unaware that the config value is expressed in centimetres.
- `find_nearest()` and its `/parking/ser-zone` `distance_meters` response are unaffected — this change only widens `find_containing()`'s decision, not the nearest-zone distance display.

## Capabilities

### New Capabilities
(none)

### Modified Capabilities
- `ser-zone-query`: `SerZone.contains()` gains a `tolerance_m` parameter and boundary-proximity semantics; `SerZoneRepository.find_containing()`'s PostgreSQL implementation applies a configurable tolerance (env var, default 50cm) instead of an exact zero-tolerance boundary check.

## Impact

- **Code**: `src/mobility_manager/domain/entities/ser_zone.py` (`contains()`), `src/mobility_manager/infrastructure/repositories/postgres/ser_zone_repo.py` (`find_containing()`), `src/mobility_manager/config.py` (new env-var getter).
- **Behavior**: `SerTicketTriggerHandler` (notifications) and `ElParkingSerTicketProvider.create_ticket()` (SER ticket creation, both the manual `POST /parking/ser-tickets` surface and any future automatic trigger) both become tolerant of GPS fixes landing up to the configured distance outside a zone's stored polygon.
- **Config surface**: one new environment variable, `SER_ZONE_CONTAINMENT_TOLERANCE_CM`, default `50`.
- **Out of scope**: disambiguating overlapping/adjacent zones when a tolerant point matches more than one (e.g. two different-coloured zones sharing a frontier) — `find_containing()` keeps returning the first match in existing iteration order; the ElParking exemption/enforcement-schedule gap for future automatic ticket creation (tracked separately, not touched here).
