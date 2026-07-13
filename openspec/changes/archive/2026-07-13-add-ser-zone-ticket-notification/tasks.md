## 1. DetermineSerTicketRequirement use case

- [x] 1.1 Create `src/mobility_manager/application/use_cases/determine_ser_ticket_requirement.py` with `DetermineSerTicketRequirement.execute(zone: SerZone | None) -> bool`, returning `zone is not None`. Docstring records the future seam (home-proximity, resident-permit, enforcement-hours factors arrive here as injected dependencies).
- [x] 1.2 Unit tests: `zone is not None` → `True`; `zone is None` → `False`.

## 2. Notification template

- [x] 2.1 In `src/mobility_manager/application/notification_templates.py`, add a new message kind (e.g. `ser_ticket_required`) to the `en` and `es` template dicts, taking `plate` and `zone_number` substitution values, stating a SER ticket must be created.
- [x] 2.2 Unit test: `render("ser_ticket_required", "es", plate=..., zone_number=...)` and the `"en"`/fallback case both substitute correctly.

## 3. Activate SerTicketTriggerHandler

- [x] 3.1 Rewrite `src/mobility_manager/application/event_handlers/ser_ticket_trigger_handler.py`: constructor takes `vehicle_repo: VehicleRepository`, `vehicle_location_repo: VehicleLocationRepository`, `user_preferences_repo: UserPreferencesRepository`, `find_containing_ser_zone: FindContainingSerZone`, `determine_ser_ticket_requirement: DetermineSerTicketRequirement`, `send_notification: SendNotification` (mirrors `NotificationDispatchHandler`'s constructor shape).
- [x] 3.2 In `handle(event)`: look up previous location via `get_previous(event.vehicle_id, before=event.received_at)`; if a previous location exists and `distance_m(...)` is below `get_notification_movement_threshold_meters()`, return silently (no zone lookup).
- [x] 3.3 Otherwise (no previous location, or distance at/above threshold): call `find_containing_ser_zone.execute(GeoLocation(lat=event.latitude, lng=event.longitude))`, then `determine_ser_ticket_requirement.execute(zone)`.
- [x] 3.4 If a ticket is required: look up the vehicle via `vehicle_repo.get_by_id(event.vehicle_id)` (skip silently if not found), look up owner preferences, render the new template with plate + `zone.zone_number`, and call `send_notification.execute(vehicle.user_id, NotificationMessage(text=..., location=GeoLocation(...)))`.
- [x] 3.5 Update the handler's module docstring to reflect it is now active (remove the "deliberately a no-op" language), following the pattern already used in `notification_dispatch_handler.py`'s docstring.

## 4. Wiring

- [x] 4.1 In `src/mobility_manager/presentation/api/app.py`, construct `DetermineSerTicketRequirement()` and update the `SerTicketTriggerHandler(...)` construction (currently `SerTicketTriggerHandler()` with no args, in the Events block around line 229) to pass `vehicle_repo`, `vehicle_location_repo`, `user_preferences_repo`, `find_containing_uc` (already constructed earlier in `lifespan`, around line 157), the new `DetermineSerTicketRequirement` instance, and `send_notification_uc`.
- [x] 4.2 Verify construction order: `find_containing_uc`, `vehicle_repo`, `vehicle_location_repo`, `user_preferences_repo`, and `send_notification_uc` must all exist before the Events block runs (confirm no reordering needed — per design.md context, they already do).

## 5. Tests

- [x] 5.1 `SerTicketTriggerHandler` unit tests (mocking all injected ports/use cases): skips when distance below threshold; checks zone on first-ever location; checks zone on genuine movement; skips notification when `DetermineSerTicketRequirement` returns `False`; sends notification with correct plate/zone_number when it returns `True`; skips silently when vehicle not found; localizes to owner's `notification_language`, falling back to default when unset.
- [x] 5.2 Confirm no ticket-provider or ticket-creation code path is exercised by any of the above (assert on absence of provider calls/mocks).

## 6. Verification

- [x] 6.1 Run `ruff check` and `mypy` on touched files.
- [x] 6.2 Run the full test suite (`pytest tests/`) and confirm no regressions beyond the known baseline `*_repo_integration.py` errors.
- [x] 6.3 Manually verify end-to-end against a running stack: move a test vehicle's reported location into a known SER zone and confirm the configured notification channel receives the "ticket required" message with correct plate/zone number, then confirm no repeat notification on a sub-threshold ping.
