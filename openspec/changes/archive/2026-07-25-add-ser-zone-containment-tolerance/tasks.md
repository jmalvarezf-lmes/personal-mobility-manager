## 1. Config

- [x] 1.1 Add `get_ser_zone_containment_tolerance_cm() -> int` to `src/mobility_manager/config.py`, reading `SER_ZONE_CONTAINMENT_TOLERANCE_CM` with int-with-fallback (default `50`), mirroring `get_vehicle_poll_interval_minutes()`'s style.
- [x] 1.2 Add `SER_ZONE_CONTAINMENT_TOLERANCE_CM=50` to `.env.example` with a one-line comment explaining it compensates for GPS positioning error.

## 2. Domain

- [x] 2.1 Add `tolerance_m: float = 0.0` parameter to `SerZone.contains()` in `src/mobility_manager/domain/entities/ser_zone.py`; return `self.geometry.covers(point) or self.geometry.distance(point) <= tolerance_m`.
- [x] 2.2 Update `SerZone.contains()`'s docstring to describe the tolerance parameter and its default.

## 3. Infrastructure

- [x] 3.1 Update `PostgresSerZoneRepository.find_containing()` in `src/mobility_manager/infrastructure/repositories/postgres/ser_zone_repo.py` to resolve `tolerance_m = get_ser_zone_containment_tolerance_cm() / 100` and pass it to every `zone.contains(location, tolerance_m=tolerance_m)` call.
- [x] 3.2 Update the module/method docstrings referencing `find_containing()`'s exactness to describe the new tolerant behavior.

## 4. Tests — Domain (unit)

- [x] 4.1 In `tests/domain/entities/test_ser_zone.py`, add a test asserting `contains()` returns `False` for a point just outside the polygon when `tolerance_m` is omitted (regression guard for the default-preserves-old-behavior contract).
- [x] 4.2 Add a test asserting `contains(location, tolerance_m=X)` returns `True` for a point outside the polygon whose distance to the boundary is `<= X`.
- [x] 4.3 Add a test asserting `contains(location, tolerance_m=X)` returns `False` for a point whose distance to the boundary is `> X`.

## 5. Tests — Infrastructure (integration, requires POSTGRES_DSN)

- [x] 5.1 In `tests/infrastructure/test_ser_zone_repo_integration.py`, add a test that inserts a zone via `bulk_replace`, queries `find_containing()` with a point just outside the polygon (within the default tolerance), and asserts the zone is returned.
- [x] 5.2 Add a test that queries `find_containing()` with a point farther outside the polygon than the tolerance and asserts `None` is returned (existing `test_find_containing_returns_none_when_outside_all_zones` already covers the far-outside case — add a near-but-beyond-tolerance case alongside it).
- [x] 5.3 Add a test overriding `SER_ZONE_CONTAINMENT_TOLERANCE_CM` (e.g. via `monkeypatch.setenv`) and asserting `find_containing()`'s tolerance changes accordingly.

## 6. Verification

- [x] 6.1 Run `make test` and confirm all non-integration tests pass.
- [x] 6.2 Run `make coverage` and confirm `domain/` stays at 100% and `application/` stays at or above 80%.
- [x] 6.3 Manually verify against the original incident: with the default tolerance, confirm `SerZone.contains()` now returns `True` for the recorded location (40.482817, -3.705411) against zone 085's stored geometry (read-only DB check, no writes).
